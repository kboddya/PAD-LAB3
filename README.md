# Лабораторная работа №3. Контейнеризация (Docker) и оркестрация (Kubernetes) приложения ShopFlow

> **Тема**: Контейнеризация микросервисной платформы **ShopFlow** из Лабораторной работы №2 и развёртывание в кластере Kubernetes (Minikube) с сетевой изоляцией внутренних сервисов.  
> **Выполнил**: Bohdan Kondratiuk.

---

## Содержание
1. [Описание проекта](#1-описание-проекта)
2. [Архитектура](#2-архитектура)
3. [Используемые технологии](#3-используемые-технологии)
4. [Установка](#4-установка)
5. [Запуск](#5-запуск)
6. [Configuration](#6-configuration)
7. [API](#7-api)
8. [Примеры использования](#8-примеры-использования)
9. [Тестирование](#9-тестирование)
10. [Результаты экспериментов и анализа конфигураций](#10-результаты-экспериментов-и-анализа-конфигураций)
11. [Выводы и ответы на вопросы к защите](#11-выводы-и-ответы-на-вопросы-к-защите)

---

## 1. Описание проекта

В данной лабораторной работе микросервисное приложение **ShopFlow** (6 бизнес-микросервисов + API Gateway + NGINX-фронтенд + PostgreSQL + RabbitMQ) полностью контейнеризировано в Docker и оформлено в виде декларативных манифестов Kubernetes (`Lab3/k8s/`).

### Ключевые особенности реализации
- **8 оптимизированных Docker-образов**:
  - `auth-service`, `user-service`, `product-service`, `order-service`, `payment-service`, `notification-service`, `api-gateway` (на базе `python:3.12-slim`, кэширование слоя `requirements.txt`, запуск под непривилегированным пользователем `appuser`).
  - `frontend` (на базе `nginxinc/nginx-unprivileged:1.27-alpine`, запуск без прав `root` на порту `8080`).
- **Строгая сетевая изоляция (Zero-Trust Perimeter)**:
  - В Docker Compose наружу открыт **только** порт `8080:8080` контейнера `frontend`; все остальные 9 контейнеров (включая `api-gateway`, базы данных и RabbitMQ) используют только внутренний `expose:` внутри сети `shopflow-net`.
  - В Kubernetes наружу через `NodePort` (`30080`) опубликован **только** `Service/frontend`; все остальные 9 сервисов имеют тип `ClusterIP` и недоступны извне кластера напрямую.
- **Полный набор K8s-ресурсов**: `Namespace`, `ConfigMap`, `Secret`, `PersistentVolumeClaim`, `Deployment` (с `livenessProbe`, `readinessProbe`, `resources.requests/limits`, `runAsNonRoot`), `Service`, `HorizontalPodAutoscaler` (`autoscaling/v2`) и единый `kustomization.yaml`.

---

## 2. Архитектура

### 2.1. Топология кластера Kubernetes (`namespace: shopflow`)

```mermaid
flowchart TB
    User([Внешний клиент / Браузер]) -->|NodePort :30080| FE_SVC[Service: frontend<br/>NodePort :8080]
    FE_SVC --> FE_POD[Deployment: frontend<br/>replicas: 2 | NGINX SPA]

    FE_POD -->|http://api-gateway:8000 /api/*| GW_SVC[Service: api-gateway<br/>ClusterIP :8000]
    GW_SVC --> GW_POD[Deployment: api-gateway<br/>replicas: 2]

    GW_POD --> AUTH[ClusterIP auth-service :8001]
    GW_POD --> USER[ClusterIP user-service :8002]
    GW_POD --> PROD[ClusterIP product-service :8003<br/>replicas: 2]
    GW_POD --> ORD[ClusterIP order-service :8004<br/>replicas: 2 + HPA 2..6]
    GW_POD --> PAY[ClusterIP payment-service :8005]
    GW_POD --> NOTIF[ClusterIP notification-service :8006]

    AUTH & USER & PROD & ORD & PAY & NOTIF --> PG[ClusterIP postgres :5432<br/>+ PVC 1Gi]
    AUTH & USER & PROD & ORD & PAY & NOTIF -.-> RMQ[ClusterIP rabbitmq :5672]
```

### 2.2. Структура `Lab3/`

```text
Lab3/
├── Instruction.md
├── PLAN.md
├── README.md
├── pytest.ini
├── docker/
│   ├── docker-compose.yml              # Запуск всего стека (снаружи открыт только frontend:8080)
│   └── build-images.sh                 # Сборка 8 Docker-образов (локально или в --minikube)
├── k8s/
│   ├── namespace.yaml                  # Namespace shopflow
│   ├── kustomization.yaml              # Единый манифест для kubectl apply -k k8s/
│   ├── configmaps/
│   │   ├── app-config.yaml             # DNS URL сервисов, LOG_LEVEL, Rate Limit
│   │   └── postgres-init.yaml          # SQL инициализации 6 БД
│   ├── secrets/
│   │   └── app-secrets.yaml            # Шаблон Secret для Minikube
│   ├── infrastructure/
│   │   ├── postgres.yaml               # PVC + Deployment + ClusterIP Service
│   │   └── rabbitmq.yaml               # Deployment + ClusterIP Service
│   ├── deployments/                    # 8 Deployment-манифестов с probes, limits и runAsNonRoot
│   ├── services/                       # 7 ClusterIP + 1 NodePort (frontend:30080)
│   └── hpa/
│       └── order-service-hpa.yaml      # HorizontalPodAutoscaler (2..6 реплик по CPU 70%)
├── scripts/
│   ├── deploy-minikube.sh              # Полное развёртывание в Minikube
│   └── demo-scaling-and-recovery.sh    # Демонстрация scale и self-healing (delete pod)
└── tests/
    └── test_k8s_and_docker.py          # Автоматическая валидация Dockerfiles, Compose и K8s
```

---

## 3. Используемые технологии

| Компонент | Технология | Назначение и обоснование |
| --- | --- | --- |
| **Контейнеризация** | **Docker** (`python:3.12-slim`, `nginxinc/nginx-unprivileged:1.27-alpine`) | Минимальный размер образов, кэширование зависимостей отдельным слоем `COPY requirements.txt`, запрет работы под `root`, `.dockerignore` исключает `.venv/`, `.git/`, `tests/`. |
| **Локальная оркестрация** | **Docker Compose** | Поднятие всех 10 контейнеров одной командой, проверка `service_healthy` перед стартом зависимых сервисов, изоляция сети `shopflow-net`. |
| **Оркестрация в кластере** | **Kubernetes / Minikube + Kustomize** | Декларативное управление репликами (`Deployment`), сервисным обнаружением через CoreDNS (`ClusterIP`), разделением конфигурации (`ConfigMap`/`Secret`), самовосстановлением и автоскейлингом (`HPA`). |

---

## 4. Установка

Для запуска требуются установленные:
- Docker Desktop / Docker Engine (`docker compose`)
- `kubectl` (проверено на `v1.33.9` с встроенным Kustomize `v5.6.0`)
- `minikube` (для локального кластера Kubernetes)

---

## 5. Запуск

### Вариант А. Проверка и запуск через Docker Compose

```bash
cd Lab3/docker
docker compose up --build
```
После старта приложение доступно в браузере по единственному внешнему адресу: **`http://localhost:8080`**.

### Вариант Б. Развёртывание в Minikube (Kubernetes)

1. Автоматизированный запуск:
   ```bash
   ./Lab3/scripts/deploy-minikube.sh
   ```
2. Или пошагово вручную:
   ```bash
   minikube start --cpus=2 --memory=4096
   ./Lab3/docker/build-images.sh --minikube
   kubectl apply -k Lab3/k8s
   kubectl get pods,services,deployments -n shopflow
   minikube service frontend -n shopflow --url
   ```

> **Примечание о среде проверки**: на данной машине Docker-демон и Minikube не были запущены в момент выполнения, поэтому проверка выполнена статически через `docker compose config --quiet`, `kubectl kustomize Lab3/k8s` и автоматический pytest-набор. Все манифесты готовы к немедленному запуску после старта Docker / Minikube.

---

## 6. Configuration

### ConfigMap (`k8s/configmaps/app-config.yaml`)
Содержит несекретные параметры и внутренние DNS-адреса Kubernetes (`http://<service-name>:<port>`, без `localhost`):
- `AUTH_SERVICE_URL=http://auth-service:8001`
- `USER_SERVICE_URL=http://user-service:8002`
- `PRODUCT_SERVICE_URL=http://product-service:8003`
- `ORDER_SERVICE_URL=http://order-service:8004`
- `PAYMENT_SERVICE_URL=http://payment-service:8005`
- `NOTIFICATION_SERVICE_URL=http://notification-service:8006`
- `RATE_LIMIT_REQUESTS=60`, `RATE_LIMIT_WINDOW_SECONDS=60`, `PROXY_TIMEOUT_SECONDS=10.0`, `LOG_LEVEL=INFO`, `LOG_JSON=true`.

### Secret (`k8s/secrets/app-secrets.yaml`)
Хранит чувствительные переменные: `POSTGRES_PASSWORD`, `JWT_SECRET`, `RABBITMQ_URL`, `AUTH_DATABASE_URL` .. `NOTIFICATION_DATABASE_URL`.  
В файле `app-secrets.yaml` приведены только тестовые значения для локального Minikube. В реальной среде Secret должен создаваться вне Git:
```bash
kubectl create secret generic shopflow-secrets -n shopflow \
  --from-literal=POSTGRES_PASSWORD='<strong-password>' \
  --from-literal=JWT_SECRET='<random-64-char-secret>' \
  --from-literal=RABBITMQ_URL='amqp://user:pass@rabbitmq:5672/'
```

---

## 7. API

Единая внешняя точка входа — `frontend` (`NodePort 30080` в Kubernetes, `:8080` в Docker Compose). NGINX отдаёт SPA-интерфейс и проксирует внутренние маршруты:
- `GET /health` — liveness/readiness самого frontend (`200 {"status":"ok","service":"frontend"}`)
- `GET /ready` → `http://api-gateway:8000/ready`
- `GET /docs`, `/openapi.json` → Swagger UI API Gateway
- `/api/auth/*`, `/api/users/*`, `/api/products/*`, `/api/orders/*`, `/api/payments/*`, `/api/notifications/*`, `/api/dashboard` → `http://api-gateway:8000/api/*`

---

## 8. Примеры использования и демонстрации (Minikube)

### Проверка состояния кластера и логов
```bash
kubectl get pods -n shopflow
kubectl get services -n shopflow
kubectl get deployments -n shopflow
kubectl logs -n shopflow deployment/api-gateway --tail=20
```

### Проверка API через Frontend NodePort
```bash
FRONTEND_URL="$(minikube service frontend -n shopflow --url)"
curl -s "${FRONTEND_URL}/health"
curl -s "${FRONTEND_URL}/ready"
curl -s "${FRONTEND_URL}/api/products"
```

### Демонстрация горизонтального масштабирования и самовосстановления
Скрипт [demo-scaling-and-recovery.sh](file:///Users/kboddya/Dev/Univ/PAD/Lab3/scripts/demo-scaling-and-recovery.sh) выполняет:
```bash
# 1. Масштабирование order-service до 4 реплик
kubectl scale deployment order-service -n shopflow --replicas=4
kubectl get pods -n shopflow -l app=order-service

# 2. Удаление одного Pod для демонстрации self-healing
kubectl delete pod <order-service-pod-name> -n shopflow
kubectl get pods -n shopflow -l app=order-service
```

---

## 9. Тестирование

Набор автотестов [test_k8s_and_docker.py](file:///Users/kboddya/Dev/Univ/PAD/Lab3/tests/test_k8s_and_docker.py) программно проверяет:
1. Наличие и корректность всех 8 `Dockerfile` и `.dockerignore` (присутствие `EXPOSE` и non-root пользователя).
2. Корректность [docker-compose.yml](file:///Users/kboddya/Dev/Univ/PAD/Lab3/docker/docker-compose.yml) (все 10 сервисов, `healthcheck` на каждом, открыт наружу только `frontend:8080`).
3. Полную сборку манифестов через `kubectl kustomize Lab3/k8s`:
   - отсутствие `localhost`/`127.0.0.1` в `ConfigMap`;
   - наличие `livenessProbe`, `readinessProbe`, `resources.requests` и `resources.limits` во всех 10 `Deployment`;
   - `securityContext.runAsNonRoot: true` на всех 8 прикладных контейнерах;
   - только `Service/frontend` имеет `type: NodePort`, остальные 9 — `ClusterIP`.

### Запуск проверок

```bash
docker compose -f Lab3/docker/docker-compose.yml config --quiet
kubectl kustomize Lab3/k8s > /dev/null
Lab2/.venv/bin/pytest Lab3/tests/test_k8s_and_docker.py -v
```
Результат: **`3 passed in 0.18s`**, `docker compose config` и `kubectl kustomize` завершились с кодом `0`.

---

## 10. Результаты экспериментов и анализа конфигураций

| Параметр оптимизации | Базовый подход | Реализованный подход в ShopFlow | Эффект |
| --- | --- | --- | --- |
| **Базовый образ и привилегии** | `python:3.12` (~1 GB), запуск от `root` | `python:3.12-slim` + `USER appuser` и `nginx-unprivileged` + `runAsNonRoot: true` | Снижение поверхности атаки и веса образа, соответствие Pod Security Standards |
| **Кэширование слоёв Dockerfile** | `COPY . .` перед `pip install` | Сначала `COPY requirements.txt` + `pip install`, затем `COPY shared` и код сервиса | Повторная сборка при правке кода переиспользует кэш зависимостей |
| **Сетевой периметр** | Открытые порты на каждом сервисе (`8000..8006`, `5432`) | Закрытые `ClusterIP` / `expose:`, единственный внешний вход `frontend:8080` | Исключён прямой доступ к БД, RabbitMQ и внутренним микросервисам |
| **Реплики и HPA** | По 1 экземпляру каждого сервиса | `replicas: 2` для `product`, `order`, `api-gateway`, `frontend` + HPA (2..6) для `order-service` | Нулевой простой при отказе одного Pod и готовность к росту нагрузки |

---

## 11. Выводы и ответы на вопросы к защите

Приложение **ShopFlow** из Лабораторной работы №2 успешно перенесено в контейнеры Docker и декларативную конфигурацию Kubernetes со строгой изоляцией сетевого периметра через `frontend`.

### Ответы на контрольные вопросы к защите

1. **Почему была выбрана именно эта технология и какие альтернативы рассматривались?**  
   Использованы Docker (`slim`/`unprivileged` образы) + Kubernetes + Kustomize, так как Kustomize встроен непосредственно в `kubectl` (`kubectl apply -k`) и не требует сторонних менеджеров шаблонов вроде Helm для базовой параметризации окружений.
2. **Как приложение масштабируется?**  
   Все 8 прикладных контейнеров являются *stateless*: горизонтальное масштабирование выполняется командой `kubectl scale deployment <name> --replicas=N` или автоматически через `HorizontalPodAutoscaler` (`order-service-hpa`), а `Service` автоматически балансирует трафик между готовыми Pod'ами (`readinessProbe`).
3. **Чем Docker отличается от виртуальной машины?**  
   Виртуальная машина эмулирует аппаратуру и запускает отдельную гостевую ОС с собственным ядром (гигабайты RAM/диска, долгий старт). Контейнер Docker разделяет ядро хостовой ОС и изолирует только процессы и файловую систему через `namespaces` и `cgroups`, благодаря чему стартует за миллисекунды и потребляет минимум ресурсов.
4. **Зачем нужен Kubernetes?**  
   Docker Compose подходит для одного хоста и разработки, тогда как Kubernetes обеспечивает оркестрацию на кластере: автоматический перезапуск упавших Pod'ов, rolling updates без простоя, service discovery через DNS, управление конфигурациями/секретами и автоскейлинг.
5. **Что делает Deployment?**  
   `Deployment` управляет `ReplicaSet` и гарантирует, что в кластере постоянно работает заданное количество (`replicas`) здоровых экземпляров Pod'ов указанной версии образа, а также обеспечивает бесшовное обновление (`RollingUpdate`) и откат.
6. **Что делает Service?**  
   Поскольку IP-адреса Pod'ов динамичны и меняются при пересоздании, `Service` предоставляет постоянное DNS-имя (например, `http://payment-service:8005`) и единый виртуальный IP, балансируя запросы между подходящими по `selector` здоровыми Pod'ами.
7. **Зачем нужны ConfigMap и Secret?**  
   Они отделяют конфигурацию и учётные данные от Docker-образа (принцип 12-Factor App): `ConfigMap` хранит обычные настройки (DNS-адреса, уровень логов), а `Secret` — пароли, токены и строки подключения к БД, позволяя менять окружение без пересборки образов.
8. **Что происходит при удалении Pod?**  
   Контроллер `ReplicaSet`, управляемый `Deployment`, обнаруживает расхождение между текущим и желаемым числом реплик (`replicas`) и немедленно планирует создание нового Pod'а взамен удалённого (*self-healing*).
9. **Как Kubernetes понимает, что сервис работает?**  
   С помощью двух независимых проб: `livenessProbe` (`GET /health`) проверяет, не завис ли процесс (при сбое kubelet перезапускает контейнер), а `readinessProbe` (`GET /ready`) проверяет готовность обслуживать трафик (подключена ли БД); пока `readinessProbe` не пройдёт, Pod не получает трафик от `Service`.
