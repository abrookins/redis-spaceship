all: redis data

data:
	mkdir data

redis: data
	docker-compose up -d
