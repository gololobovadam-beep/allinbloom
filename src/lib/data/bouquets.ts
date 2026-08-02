import type { Bouquet, CatalogResponse, CatalogType } from "@/lib/api-types";
import {
  CATALOG_SORT_VALUES,
  BOUQUET_TYPE_FILTERS,
  FLOWER_TYPES,
} from "@/lib/constants";
import { apiFetch } from "@/lib/api-server";

export type CatalogSearchParams = {
  entry?: string;
  catalogType?: CatalogType | string;
  flower?: string;
  color?: string;
  bouquetType?: string;
  style?: string; // legacy URL compatibility
  mixed?: string; // legacy URL compatibility
  min?: string;
  max?: string;
  sort?: string;
  filter?: string;
};

export type CatalogPagination = {
  cursor?: string;
  take?: number;
};

const toNumber = (value?: string) => {
  if (!value) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
};

const normalizeEnum = <T extends readonly string[]>(
  value: string | undefined,
  allowed: T
) => {
  if (!value) return undefined;
  const upper = value.toUpperCase();
  return (allowed as readonly string[]).includes(upper) ? upper : undefined;
};

const normalizeFlowerFilters = (value?: string) => {
  if (!value) return undefined;

  const values = value
    .split(",")
    .map((item) => normalizeEnum(item, FLOWER_TYPES))
    .filter((item): item is (typeof FLOWER_TYPES)[number] => Boolean(item));

  const unique = values.filter((item, index) => values.indexOf(item) === index);
  if (!unique.length) return undefined;
  return unique.map((item) => item.toLowerCase()).join(",");
};

const normalizeBouquetTypeFilter = (
  bouquetType?: string,
  mixed?: string,
  style?: string
) => {
  const normalized = String(bouquetType || "").trim().toLowerCase();
  const mixedLegacy = String(mixed || "").trim().toLowerCase();
  const styleLegacy = String(style || "").trim().toLowerCase();

  if (
    (BOUQUET_TYPE_FILTERS as readonly string[]).includes(normalized) &&
    normalized !== "all"
  ) {
    return normalized;
  }
  if (mixedLegacy === "mono" || mixedLegacy === "mixed") {
    return mixedLegacy;
  }
  if (styleLegacy === "season") {
    return "season";
  }
  return undefined;
};

const normalizeSortValue = (value?: string) => {
  if (!value) return undefined;
  const normalized = String(value).trim().toLowerCase();
  return (CATALOG_SORT_VALUES as readonly string[]).includes(normalized)
    ? normalized
    : undefined;
};

const normalizeCatalogType = (value?: CatalogType | string) => {
  const normalized = String(value || "").trim().toUpperCase();
  return ["FLOWERS", "BALOONS", "GIFTS", "EVENT_SPACE"].includes(normalized)
    ? (normalized as CatalogType)
    : undefined;
};

export async function getFeaturedBouquets(): Promise<Bouquet[]> {
  const response = await apiFetch("/api/catalog?filter=featured&take=6");
  if (!response.ok) return [];
  const data = (await response.json()) as CatalogResponse;
  return (data.items || []).map((item) => item.bouquet);
}

export async function getBouquetById(
  id: string,
  catalogType: CatalogType = "FLOWERS"
): Promise<Bouquet | null> {
  const params = new URLSearchParams({ catalogType });
  const response = await apiFetch(
    `/api/bouquets/${id}?${params.toString()}`,
    {},
    true
  );
  if (!response.ok) return null;
  return response.json();
}

export async function getAdminBouquets(
  catalogType: CatalogType = "FLOWERS"
): Promise<Bouquet[]> {
  const params = new URLSearchParams({
    include_inactive: "true",
    catalogType,
  });
  const response = await apiFetch(`/api/bouquets?${params.toString()}`, {}, true);
  if (!response.ok) return [];
  return response.json();
}

export async function getBouquets(
  filters: CatalogSearchParams = {},
  pagination: CatalogPagination = {}
): Promise<Bouquet[]> {
  const flowerTypes = normalizeFlowerFilters(filters.flower);
  const bouquetType = normalizeBouquetTypeFilter(
    filters.bouquetType,
    filters.mixed,
    filters.style
  );
  const min = toNumber(filters.min);
  const max = toNumber(filters.max);
  const sort = normalizeSortValue(filters.sort);
  const catalogType = normalizeCatalogType(filters.catalogType);
  const { cursor, take } = pagination;

  const params = new URLSearchParams();
  if (filters.filter) params.set("filter", filters.filter);
  if (catalogType) params.set("catalogType", catalogType);
  if (flowerTypes) params.set("flower", flowerTypes);
  if (filters.color) params.set("color", filters.color);
  if (bouquetType) params.set("bouquetType", bouquetType);
  if (min !== undefined) params.set("min", String(min));
  if (max !== undefined) params.set("max", String(max));
  if (sort) params.set("sort", sort);
  if (cursor) params.set("cursor", cursor);
  if (take) params.set("take", String(take));

  const response = await apiFetch(`/api/catalog?${params.toString()}`);
  if (!response.ok) return [];
  const data = (await response.json()) as CatalogResponse;
  return (data.items || []).map((item) => item.bouquet);
}
