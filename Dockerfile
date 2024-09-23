# syntax=docker/dockerfile:1
FROM nixos/nix:2.24.7 AS builder

RUN echo 'extra-experimental-features = nix-command flakes' >> /etc/nix/nix.conf \
  && echo 'filter-syscalls = false' >> /etc/nix/nix.conf
RUN nix-env -iA cachix -f https://cachix.org/api/v1/install
RUN --mount=type=secret,id=CACHIX_CACHE_NAME,env=CACHIX_CACHE_NAME \
  [[ ! $CACHIX_CACHE_NAME ]] || cachix use $CACHIX_CACHE_NAME

WORKDIR /work

COPY flake.* /work
RUN nix develop --profile /tmp/profile -c true
RUN --mount=type=secret,id=CACHIX_AUTH_TOKEN,env=CACHIX_AUTH_TOKEN \
  --mount=type=secret,id=CACHIX_CACHE_NAME,env=CACHIX_CACHE_NAME \
  [[ ! $CACHIX_CACHE_NAME ]] || cachix push $CACHIX_CACHE_NAME /tmp/profile

COPY . /work
RUN nix develop -c pants package ::

FROM python:3.10-slim
COPY --from=builder /work/dist/app.pex /bin/tinyalert
WORKDIR /work
ENTRYPOINT ["/bin/tinyalert"]
