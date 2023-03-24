WORK_UID  = $(shell id -u)
WORK_GID  = $(shell id -g)
HOSTIP = $(shell docker inspect bridge -f '{{range .IPAM.Config}}{{.Gateway}}{{end}}')

PROXY_IMAGENAME = local/porcupine:0.1
REDIS_IMAGENAME = bitnami/redis:latest
REDIS_CONTAINER = porcupine-redis-001
PROXY_BIND = 127.4.0.1:8096
REDIS_BIND = 127.4.0.1:6379

.PHONY: build-image
build-image:
	docker build . -t $(PROXY_IMAGENAME) \
		--build-arg WORK_UID=$(WORK_UID) --build-arg WORK_GID=$(WORK_GID)

.PHONY: build-dev
build-dev:
	mkdir -p venv && \
		docker run --rm -v "${PWD}/venv:/venv" \
			-v "${PWD}/requirements.pip:/requirements.pip" \
			--entrypoint '' $(PROXY_IMAGENAME) \
				sh -c 'python -m venv /venv && \
				/venv/bin/python -m pip install -U pip && \
				/venv/bin/python -m pip install -r /requirements.pip && \
				/venv/bin/python -m pip install mypy pylint'

.PHONY: start-dev
start-dev:
	PROXY_BIND=$(PROXY_BIND) && docker run --rm --network host \
		-v "${PWD}/porcupine:/app/porcupine" -v "${PWD}/venv:/venv" \
		-e BIND_ADDR=$${PROXY_BIND%:*} \
		-e BIND_PORT=$${PROXY_BIND#*:} \
		-e REDIS_URL=redis://$(REDIS_BIND) -e LOGLEVEL=DEBUG \
		-d $(PROXY_IMAGENAME)

.PHONY: start-dev-shell
start-dev-shell:
	IMAGENAME=$(PROXY_IMAGENAME) cli/shell

.PHONY: start
start:
	PROXY_BIND=$(PROXY_BIND) && docker run --rm --network host \
		-e BIND_ADDR=$${PROXY_BIND%:*} \
		-e BIND_PORT=$${PROXY_BIND#*:} \
		-e REDIS_URL=redis://$(REDIS_BIND) \
		-d $(PROXY_IMAGENAME)

.PHONY: start-redis
start-redis:
	docker run --rm -p $(REDIS_BIND):6379 --name $(REDIS_CONTAINER) \
		-e ALLOW_EMPTY_PASSWORD=yes \
		-d $(REDIS_IMAGENAME)

.PHONY: stop-redis
stop-redis:
	docker rm -f $(REDIS_CONTAINER)

.PHONY: clean-dev
clean-dev:
	rm -rf venv
