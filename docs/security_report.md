# Отчёт по аудиту безопасности Kubernetes-манифестов (`Lab3`)

**Методология**: Автоматизированный аудит [scripts/k8s_security_audit.py](file:///Users/kboddya/Dev/Univ/PAD/Lab3/scripts/k8s_security_audit.py) итогового вывода `kubectl kustomize Lab3/k8s` на соответствие стандартам **CIS Kubernetes Benchmark** и **Pod Security Standards (Restricted)**.

- **Замер ДО исправлений** ([security_before.json](file:///Users/kboddya/Dev/Univ/PAD/Lab3/experiments/security_before.json), `2026-11-22T20:35:11Z`): **0/4 PASS, 4 FAIL**
- **Замер ПОСЛЕ исправлений** ([security_after.json](file:///Users/kboddya/Dev/Univ/PAD/Lab3/experiments/security_after.json), `2026-11-22T20:40:08Z`): **4/4 PASS, 0 FAIL**

---

## Сравнительная таблица результатов (До и После)

| ID | Проверка (Стандарт) | Критичность | Статус ДО | Доказательство ДО | Статус ПОСЛЕ | Доказательство ПОСЛЕ |
| --- | --- | --- | --- | --- | --- | --- |
| `K8S-01` | Отсутствие захардкоженных паролей в манифесте RabbitMQ (`CIS 5.4.1`) | **High** | **FAIL** | В `rabbitmq.yaml` заданы открытые `RABBITMQ_DEFAULT_USER`/`PASS` (`guest`) | **PASS** | Учётные данные передаются через `secretKeyRef: shopflow-secrets` |
| `K8S-02` | Принцип наименьших привилегий для `Secret` (`CIS 5.4.2`) | **High** | **FAIL** | Все 7 backend/gateway сервисов монтировали весь `shopflow-secrets` через `envFrom` (доступ к DSN чужих БД) | **PASS** | Точечный `secretKeyRef`: каждый сервис получает только свой `DATABASE_URL` и нужные ключи |
| `K8S-03` | Профиль контейнеров `Pod Security Standards: Restricted` | **Medium** | **FAIL** | Во всех 8 Deployment отсутствовали `capabilities.drop=["ALL"]` и `seccompProfile: RuntimeDefault` | **PASS** | Все 8 прикладных Deployment сбрасывают `ALL` capabilities, используют `RuntimeDefault` seccomp и числовые UID (`10001`/`101`) |
| `K8S-04` | Сетевая микросегментация `NetworkPolicy` (`CIS 5.3.2`) | **High** | **FAIL** | Найдено `0` политик `NetworkPolicy` (`default-deny=False`) | **PASS** | Добавлено `11` политик `NetworkPolicy` (включая `default-deny-ingress` и точечные правила между слоями) |

---

## Внесённые исправления и живая проверка

1. Создан файл [network-policies.yaml](file:///Users/kboddya/Dev/Univ/PAD/Lab3/k8s/network-policies/network-policies.yaml): политика `default-deny-ingress` блокирует весь входящий трафик в namespace `shopflow` по умолчанию, разрешая только явные маршруты (`frontend` → `api-gateway` → микросервисы → `postgres`/`rabbitmq`). `frontend` и `api-gateway` не имеют сетевого доступа к `postgres` и `rabbitmq`.
2. Обновлены все 8 манифестов в [k8s/deployments/](file:///Users/kboddya/Dev/Univ/PAD/Lab3/k8s/deployments): `envFrom: secretRef` заменён на минимально необходимые `secretKeyRef`, добавлены `capabilities.drop: ["ALL"]` и `seccompProfile.type: RuntimeDefault`.
3. Обновлён [rabbitmq.yaml](file:///Users/kboddya/Dev/Univ/PAD/Lab3/k8s/infrastructure/rabbitmq.yaml): логин и пароль вынесены в [app-secrets.yaml](file:///Users/kboddya/Dev/Univ/PAD/Lab3/k8s/secrets/app-secrets.yaml).
4. После развёртывания обновлённых манифестов в живом кластере **OrbStack Kubernetes** (`./Lab3/scripts/deploy-k8s.sh`) все 14 Pod'ов, 11 `NetworkPolicy` и сквозной поток через `http://localhost:30080` отработали успешно (включая блокировку саморегистрации `admin` и слабых паролей с `HTTP 422` и наличие CSP/security-заголовков на NGINX и Gateway).
