# Thin Supervisor wrapper over mega-yfue/ha-eufy-sdk-bridge.
ARG BUILD_FROM=ghcr.io/mega-yfue/ha-eufy-sdk-bridge:latest
FROM ${BUILD_FROM}

RUN apk add --no-cache curl jq

COPY run.sh /run.sh
RUN chmod +x /run.sh

LABEL \
    org.opencontainers.image.title="Home Assistant Add-on: Eufy Cameras Bridge" \
    org.opencontainers.image.description="Mega SDK bridge for the Eufy Cameras integration." \
    org.opencontainers.image.source="https://github.com/mirimalulkasif/ha-eufy" \
    org.opencontainers.image.licenses="MIT"

CMD [ "/run.sh" ]
