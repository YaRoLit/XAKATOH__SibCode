from pydantic import BaseModel, Field, field_validator


class Comparable(BaseModel):
    title: str
    address: str
    price: int
    area_m2: float | None = None
    land_sotka: float | None = None
    condition: str
    completion_percent: int | None = None
    source_name: str = "demo_listing_site"
    url: str | None = None
    note: str | None = None
    is_mock: bool = True

    @field_validator("url")
    @classmethod
    def drop_fake_url(cls, value: str | None) -> None:
        return None


class PriceMockResult(BaseModel):
    value_min: int
    value_point: int
    value_max: int
    currency: str = "RUB"
    justification: str
    comparables: list[Comparable] = Field(min_length=3, max_length=6)
    confidence: float | None = None

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return max(0.0, min(1.0, float(value)))


def validate_result(result: PriceMockResult) -> None:
    if not (result.value_min <= result.value_point <= result.value_max):
        raise ValueError(
            f"Некорректный диапазон: {result.value_min} <= {result.value_point} <= {result.value_max}"
        )
    if not result.justification.strip():
        raise ValueError("Пустое обоснование")
    if len(result.comparables) < 3 or len(result.comparables) > 6:
        raise ValueError("Нужно от 3 до 6 аналогов")
