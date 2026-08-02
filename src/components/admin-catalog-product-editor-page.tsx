import Link from "next/link";
import { notFound } from "next/navigation";
import type { CatalogType } from "@/lib/api-types";
import { getBouquetById } from "@/lib/data/bouquets";
import { createCatalogProduct, updateCatalogProduct } from "@/app/admin/actions";
import AdminCatalogProductForm from "@/components/admin-catalog-product-form";

type ManagedCatalogType = Extract<CatalogType, "BALOONS" | "GIFTS" | "EVENT_SPACE">;

type AdminCatalogProductEditorPageProps = {
  catalogType: ManagedCatalogType;
  label: string;
  basePath: string;
  id?: string;
};

export default async function AdminCatalogProductEditorPage({
  catalogType,
  label,
  basePath,
  id,
}: AdminCatalogProductEditorPageProps) {
  const product = id ? await getBouquetById(id, catalogType) : undefined;
  if (id && !product) notFound();
  const isEditing = Boolean(product);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.32em] text-stone-500">
            {isEditing ? `Edit ${label}` : `New ${label}`}
          </p>
          <h1 className="text-2xl font-semibold text-stone-900 sm:text-3xl">
            {isEditing ? product?.name : `Add a ${label}`}
          </h1>
        </div>
        <Link
          href={basePath}
          className="inline-flex h-11 w-full items-center justify-center rounded-full border border-stone-300 bg-white/80 px-4 text-center text-xs uppercase tracking-[0.3em] text-stone-600 sm:w-auto"
        >
          Back to {label}s
        </Link>
      </div>
      <AdminCatalogProductForm
        key={product?.id || `new-${catalogType}`}
        catalogType={catalogType}
        product={product || undefined}
        action={isEditing ? updateCatalogProduct : createCatalogProduct}
      />
    </div>
  );
}
