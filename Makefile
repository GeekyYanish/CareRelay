.PHONY: demo down logs seed test test-api test-web test-e2e build generate-types verify-lyzr

demo:
	@test -f .env || cp .env.example .env
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api web

seed:
	docker compose exec api python -m app.seed

test: test-api test-web test-e2e

test-api:
	cd apps/api && .venv/bin/python -m pytest -q

test-web:
	pnpm --filter @carerelay/web test -- --run

test-e2e:
	pnpm --filter @carerelay/web test:e2e

build:
	pnpm --filter @carerelay/web build

generate-types:
	pnpm generate:api-types

verify-lyzr:
	docker compose exec api python -m app.verify_lyzr
