"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { parseBouquetForm, parseCatalogProductForm } from "@/lib/bouquet-form";
import { requireAdmin } from "@/lib/auth-session";
import { apiFetch } from "@/lib/api-server";

const getApiErrorMessage = async (response: Response, fallback: string) => {
  const body = (await response.json().catch(() => null)) as
    | { detail?: string | Array<{ msg?: string }>; error?: { message?: string } }
    | null;
  const detail = body?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => item?.msg?.trim())
      .filter((message): message is string => Boolean(message));
    if (messages.length) return messages.join(" ");
  }
  return body?.error?.message?.trim() || fallback;
};

export async function createBouquet(formData: FormData) {
  await requireAdmin();
  const data = parseBouquetForm(formData);
  const response = await apiFetch(
    "/api/bouquets",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
    true
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, "Unable to create bouquet."));
  }
  revalidatePath("/admin");
  redirect("/admin?toast=bouquet-added");
}

export async function updateBouquet(formData: FormData) {
  await requireAdmin();
  const id = String(formData.get("id") || "");
  const data = parseBouquetForm(formData);
  const response = await apiFetch(
    `/api/bouquets/${id}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
    true
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, "Unable to update bouquet."));
  }
  revalidatePath("/admin");
  redirect("/admin");
}

export async function deleteBouquet(formData: FormData) {
  await requireAdmin();
  const id = String(formData.get("id") || "");
  const response = await apiFetch(`/api/bouquets/${id}`, { method: "DELETE" }, true);
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, "Unable to delete bouquet."));
  }
  revalidatePath("/admin");
}

const resolveCatalogAdminPath = (value: FormDataEntryValue | null) => {
  const catalogType = String(value || "").trim().toUpperCase();
  if (catalogType === "GIFTS") {
    return { catalogType, adminPath: "/admin/gifts", storefrontPath: "/gifts" };
  }
  if (catalogType === "EVENT_SPACE") {
    return {
      catalogType,
      adminPath: "/admin/event-space",
      storefrontPath: "/event-space",
    };
  }
  if (catalogType === "BALOONS") {
    return { catalogType, adminPath: "/admin/balloons", storefrontPath: "/balloons" };
  }
  return { catalogType: "FLOWERS", adminPath: "/admin", storefrontPath: "/catalog" };
};

export async function createCatalogProduct(formData: FormData) {
  await requireAdmin();
  const route = resolveCatalogAdminPath(formData.get("catalogType"));
  const data = parseCatalogProductForm(formData);
  const response = await apiFetch(
    "/api/bouquets",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
    true
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, "Unable to create catalog product."));
  }
  revalidatePath(route.adminPath);
  revalidatePath(route.storefrontPath);
  redirect(`${route.adminPath}?toast=product-added`);
}

export async function updateCatalogProduct(formData: FormData) {
  await requireAdmin();
  const id = String(formData.get("id") || "").trim();
  const route = resolveCatalogAdminPath(formData.get("catalogType"));
  if (!id) {
    throw new Error("Missing catalog product ID.");
  }
  const data = parseCatalogProductForm(formData);
  const response = await apiFetch(
    `/api/bouquets/${encodeURIComponent(id)}?catalogType=${route.catalogType}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    },
    true
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, "Unable to update catalog product."));
  }
  revalidatePath(route.adminPath);
  revalidatePath(route.storefrontPath);
  redirect(route.adminPath);
}

export async function deleteCatalogProduct(formData: FormData) {
  await requireAdmin();
  const id = String(formData.get("id") || "").trim();
  const route = resolveCatalogAdminPath(formData.get("catalogType"));
  if (!id) {
    throw new Error("Missing catalog product ID.");
  }
  const response = await apiFetch(
    `/api/bouquets/${encodeURIComponent(id)}?catalogType=${route.catalogType}`,
    { method: "DELETE" },
    true
  );
  if (!response.ok) {
    throw new Error(await getApiErrorMessage(response, "Unable to delete catalog product."));
  }
  revalidatePath(route.adminPath);
  revalidatePath(route.storefrontPath);
}
