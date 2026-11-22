# Лабораторная работа №3. Docker и Kubernetes

## 1. Цель работы

В третьей лабораторной необходимо взять приложение из **лабораторной работы №2**, контейнеризировать его и развернуть с использованием системы оркестрации контейнеров.

Допускается использовать:

* Kubernetes;
* Minikube.

---

# 2. Docker

Каждый backend-микросервис должен быть контейнеризирован.

Например:

```text
Auth Service
      ↓
Docker Image

User Service
      ↓
Docker Image

Order Service
      ↓
Docker Image

...
```

Для каждого сервиса необходимо предоставить `Dockerfile`.

---

# 3. Dockerfile

Dockerfile должен быть оптимизирован.

Необходимо учитывать:

* небольшой размер image;
* использование `.dockerignore`;
* caching слоёв;
* отсутствие секретов внутри image;
* запуск приложения не от root, если это возможно;
* корректный CMD/ENTRYPOINT.

Пример структуры:

```text
service/
├── Dockerfile
├── .dockerignore
├── requirements.txt
└── src/
```

---

# 4. Docker Compose

Перед Kubernetes рекомендуется проверить приложение через Docker Compose.

Пример:

```text
docker-compose.yml

        ┌──────────────┐
        │ API Gateway  │
        └───────┬──────┘
                │
     ┌──────────┼──────────┐
     ▼          ▼          ▼
   Auth       User       Order
 Service     Service     Service
     │          │          │
     ▼          ▼          ▼
   DB/Auth    DB/User    DB/Order
```

Compose должен позволять поднять всю систему одной командой.

Например:

```bash
docker compose up --build
```

---

# 5. Kubernetes

Необходимо подготовить Kubernetes manifests.

Минимально рекомендуется использовать:

```text
Deployment
Service
ConfigMap
Secret
```

Для каждого backend-сервиса должен существовать Kubernetes Deployment.

Например:

```text
k8s/
├── namespace.yaml
├── auth/
│   ├── deployment.yaml
│   └── service.yaml
├── user/
│   ├── deployment.yaml
│   └── service.yaml
├── order/
│   ├── deployment.yaml
│   └── service.yaml
├── payment/
│   ├── deployment.yaml
│   └── service.yaml
├── notification/
│   ├── deployment.yaml
│   └── service.yaml
├── gateway/
│   ├── deployment.yaml
│   └── service.yaml
├── configmap.yaml
└── secret.yaml
```

Структура может отличаться.

---

# 6. Deployment

Для каждого сервиса необходимо создать Deployment.

Deployment должен описывать:

* Docker image;
* количество replicas;
* container port;
* environment variables;
* resources;
* health checks.

Например:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: user-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: user-service
  template:
    metadata:
      labels:
        app: user-service
    spec:
      containers:
        - name: user-service
          image: user-service:latest
          ports:
            - containerPort: 8000
```

---

# 7. Kubernetes Service

Для взаимодействия между сервисами необходимо использовать Kubernetes Services.

Например:

```text
order-service
      │
      │ HTTP
      ▼
payment-service
```

В Kubernetes:

```text
http://payment-service:8000
```

Сервисы не должны обращаться друг к другу через `localhost`.

---

# 8. ConfigMap

Конфигурационные параметры необходимо вынести из Docker image.

Например:

```text
DATABASE_HOST
DATABASE_PORT
LOG_LEVEL
SERVICE_URL
```

должны задаваться через environment variables / ConfigMap.

---

# 9. Secrets

Пароли, токены и другие секретные значения нельзя хранить непосредственно в исходном коде.

Например:

```text
DATABASE_PASSWORD
JWT_SECRET
API_KEY
```

не должны находиться в Git в открытом виде.

Для Kubernetes необходимо использовать `Secret`.

---

# 10. Health Checks

Каждый сервис должен иметь health endpoints.

Например:

```text
/health
/ready
```

В Kubernetes необходимо использовать:

```text
livenessProbe
readinessProbe
```

Пример:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000

readinessProbe:
  httpGet:
    path: /ready
    port: 8000
```

---

# 11. Resource Limits

Для контейнеров необходимо задать ограничения ресурсов.

Например:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "512Mi"
```

Конкретные значения должны зависеть от вашего приложения.

---

# 12. Масштабирование

Необходимо продемонстрировать возможность горизонтального масштабирования хотя бы одного сервиса.

Например:

```bash
kubectl scale deployment order-service --replicas=3
```

После этого:

```text
             ┌─ order-service
             │
Request ─────┼─ order-service
             │
             └─ order-service
```

---

# 13. Запуск в Minikube

Пример последовательности запуска:

```bash
minikube start
```

Далее необходимо загрузить/собрать Docker images.

После этого:

```bash
kubectl apply -f k8s/
```

Проверка:

```bash
kubectl get pods
```

```bash
kubectl get services
```

```bash
kubectl get deployments
```

---

# 14. Демонстрация работы

Во время защиты необходимо показать:

### 1. Все Pod'ы

```bash
kubectl get pods
```

### 2. Все Services

```bash
kubectl get services
```

### 3. Deployments

```bash
kubectl get deployments
```

### 4. Логи

```bash
kubectl logs <pod>
```

### 5. Работа API

Необходимо выполнить несколько реальных запросов к приложению.

### 6. Масштабирование

Показать изменение количества replicas.

### 7. Восстановление

Желательно удалить один Pod:

```bash
kubectl delete pod <pod>
```

и показать, что Kubernetes автоматически создаёт новый Pod.

---

# 15. Что необходимо предоставить

Пример структуры:

```text
lab3/
├── README.md
├── docker/
└── k8s/
    ├── namespace.yaml
    ├── deployments/
    ├── services/
    ├── configmaps/
    └── secrets/
```

---

# 16. Критерии оценивания лабораторной №3

| Критерий                           | Вес |
| ---------------------------------- | --: |
| Dockerfile для сервисов            | 15% |
| Docker Compose                     | 10% |
| Kubernetes Deployments             | 20% |
| Kubernetes Services                | 15% |
| ConfigMap / Secrets                | 10% |
| Health checks                      | 10% |
| Resource limits                    |  5% |
| Масштабирование                    |  5% |
| Демонстрация работы и документация | 10% |

---

# Общие требования к оформлению

## Git

Все лабораторные работы должны находиться в Git-репозитории.

Коммиты должны отражать процесс разработки.

Не рекомендуется использовать единственный commit вида:

```text
final project
```

Желательно делать осмысленные commits:

```text
feat: add docker configuration
feat: add kubernetes deployment
```

---

# README

Лабораторная работа должна иметь собственный README.

README должен содержать:

```text
1. Описание проекта
2. Архитектура
3. Используемые технологии
4. Установка
5. Запуск
6. Configuration
7. API
8. Примеры использования
9. Тестирование
10. Результаты экспериментов
11. Выводы
```

---

# Общие требования к защите

На защите студент должен не только показать работающий проект, но и **объяснить архитектурные решения**.

Необходимо быть готовым ответить на вопросы:

* Почему была выбрана именно эта технология?
* Какие альтернативы рассматривались?
* Как приложение масштабируется?
* Чем Docker отличается от виртуальной машины?
* Зачем нужен Kubernetes?
* Что делает Deployment?
* Что делает Service?
* Зачем нужны ConfigMap и Secret?
* Что происходит при удалении Pod?
* Как Kubernetes понимает, что сервис работает?

## Главное

Лабораторные работы оцениваются не только по принципу **«код запускается»**.

Высоко оцениваются:

* самостоятельность;
* понимание используемых технологий;
* качество архитектуры;
* эксперименты;
* сравнение альтернатив;
* анализ результатов;
* корректная документация;
* способность объяснить принятые решения.

**Цель лабораторной — не просто собрать работающий проект, а показать понимание современных подходов к контейнеризации и оркестрации распределённых приложений.**
