"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { parseBouquetForm, parseCatalogProductForm } from "@/lib/bouquet-form";
import { requireAdmin } from "@/lib/auth-session";
import { apiFetch } from "@/lib/api-server";

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
    throw new Error("Unable to create bouquet.");
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
    throw new Error("Unable to update bouquet.");
  }
  revalidatePath("/admin");
  redirect("/admin");
}

export async function deleteBouquet(formData: FormData) {
  await requireAdmin();
  const id = String(formData.get("id") || "");
  const response = await apiFetch(`/api/bouquets/${id}`, { method: "DELETE" }, true);
  if (!response.ok) {
    throw new Error("Unable to delete bouquet.");
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
    throw new Error("Unable to create catalog product.");
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
    throw new Error("Unable to update catalog product.");
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
    throw new Error("Unable to delete catalog product.");
  }
  revalidatePath(route.adminPath);
  revalidatePath(route.storefrontPath);
}
