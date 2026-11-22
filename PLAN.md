# План реализации Лабораторной работы №3: Docker и Kubernetes для ShopFlow (`Lab3/`)

## 1. Цель работы
Контейнеризировать микросервисную платформу **ShopFlow** из Лабораторной работы №2 (6 бизнес-микросервисов, API Gateway, NGINX-фронтенд, PostgreSQL и RabbitMQ) и подготовить полный набор production-ориентированных Kubernetes-манифестов для развёртывания, масштабирования и самовосстановления в Minikube / Kubernetes.

---

## 2. Сетевая модель и принцип изоляции

Вся внутренняя инфраструктура полностью изолирована:
- **PostgreSQL (`5432`)**, **RabbitMQ (`5672`/`15672`)**, **6 бизнес-микросервисов (`8001`–`8006`)** и **`api-gateway` (`8000`)** используют исключительно `ClusterIP` Services (в Kubernetes) и внутренний `expose:` без `ports:` (в Docker Compose).
- Наружу открыт **единственный вход** — сервис **`frontend` (`NGINX`, порт `8080`, `NodePort 30080`)**, который отдаёт SPA-интерфейс и проксирует `/api/*`, `/ready`, `/docs` на `http://api-gateway:8000`.
- Все межсервисные обращения используют исключительно DNS-имена сервисов (`http://user-service:8002`, `postgres`, `rabbitmq`), без `localhost`.

---

## 3. Архитектурный состав ресурсов `Lab3/`

1. **`docker/`**:
   - `docker-compose.yml` — сборка всех 8 сервисов из `../../Lab2` с healthchecks и закрытыми внутренними портами.
   - `build-images.sh` — скрипт сборки Docker-образов `shopflow/<service>:1.0.0` (поддерживает `--minikube`).
2. **`k8s/`**:
   - `namespace.yaml` — изолированный namespace `shopflow`.
   - `configmaps/` — `shopflow-config` (DNS URLs, rate limits, логирование) и `postgres-init-sql` (SQL создания 6 БД).
   - `secrets/` — `shopflow-secrets` (пароли, JWT секрет, DSN баз данных — шаблон для локального Minikube).
   - `infrastructure/` — `postgres` (PVC + Deployment + ClusterIP) и `rabbitmq` (Deployment + ClusterIP).
   - `deployments/` — 8 Deployment-манифестов (`requests`/`limits`, `livenessProbe`, `readinessProbe`, `runAsNonRoot: true`).
   - `services/` — 7 `ClusterIP` сервисов и 1 `NodePort` (`frontend`, порт `30080`).
   - `hpa/` — `HorizontalPodAutoscaler` (`autoscaling/v2`) для `order-service`.
   - `kustomization.yaml` — единое развёртывание через `kubectl apply -k k8s/`.
3. **`scripts/`**:
   - `deploy-minikube.sh` — сборка образов в Docker daemon Minikube и применение манифестов.
   - `demo-scaling-and-recovery.sh` — демонстрация `kubectl scale` и удаления Pod (`self-healing`).
4. **`tests/test_k8s_and_docker.py`**:
   - Автоматическая валидация всех Dockerfile, Compose и K8s YAML (probes, resource limits, DNS-адресация, сетевая изоляция).
