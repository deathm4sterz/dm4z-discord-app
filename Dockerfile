FROM	rust:1.93.1-alpine3.20	AS	app-build

WORKDIR	/opt

RUN	apk update && \
	apk add make gcc g++ libressl-dev

COPY	Cargo.toml Cargo.lock	./

COPY	.	.

RUN	cargo build --release

FROM	scratch	AS	runtime

COPY --from=app-build	/opt/target/release/baburao	/usr/bin/

CMD	[ "/usr/bin/baburao" ]
