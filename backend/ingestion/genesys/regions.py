"""Regiones de Genesys Cloud y su dominio (`login.<dominio>` para OAuth y `api.<dominio>` para la API).

Fuente: https://developer.genesys.cloud/platform/api/ (tabla de regiones). `GENESYS_REGION` admite el nombre de la región
(`eu-west-1`) o directamente el dominio (`mypurecloud.ie`).
"""
REGIONS = {
    "us-east-1": "mypurecloud.com",
    "us-east-2": "use2.us-gov-pure.cloud",
    "us-west-2": "usw2.pure.cloud",
    "ca-central-1": "cac1.pure.cloud",
    "sa-east-1": "sae1.pure.cloud",
    "eu-west-1": "mypurecloud.ie",
    "eu-west-2": "euw2.pure.cloud",
    "eu-central-1": "mypurecloud.de",
    "eu-central-2": "euc2.pure.cloud",
    "me-central-1": "mec1.pure.cloud",
    "ap-south-1": "aps1.pure.cloud",
    "ap-northeast-1": "mypurecloud.jp",
    "ap-northeast-2": "apne2.pure.cloud",
    "ap-northeast-3": "apne3.pure.cloud",
    "ap-southeast-2": "mypurecloud.com.au",
}


class GenesysConfigError(ValueError):
    pass


def api_host(region: str) -> str:
    region = region.strip().lower()
    if region in REGIONS:
        return REGIONS[region]
    if region in REGIONS.values():
        return region
    raise GenesysConfigError(f"Región de Genesys desconocida: {region!r}")
