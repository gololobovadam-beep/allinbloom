import Link from "next/link";
import type { CatalogType } from "@/lib/api-types";
import { getAdminBouquets } from "@/lib/data/bouquets";
import AdminCatalogProductsPanel from "@/components/admin-catalog-products-panel";

type ManagedCatalogType = Extract<CatalogType, "BALOONS" | "GIFTS" | "EVENT_SPACE">;

type AdminCatalogManagementPageProps = {
  catalogType: ManagedCatalogType;
  title: string;
  label: string;
  basePath: string;
};

export default async function AdminCatalogManagementPage({
  catalogType,
  title,
  label,
  basePath,
}: AdminCatalogManagementPageProps) {
  const products = await getAdminBouquets(catalogType);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.32em] text-stone-500">Admin studio</p>
          <h1 className="text-2xl font-semibold text-stone-900 sm:text-3xl">{title}</h1>
        </div>
        <Link
          href={`${basePath}/new`}
          className="inline-flex h-11 w-full items-center justify-center rounded-full bg-[color:var(--brand)] px-5 text-center text-xs uppercase tracking-[0.3em] text-white transition hover:bg-[color:var(--brand-dark)] sm:w-auto"
        >
          Add {label.slice(0, -1)}
        </Link>
      </div>
      <div className="glass rounded-[28px] border border-white/80 p-4 sm:p-6">
        <AdminCatalogProductsPanel
          products={products}
          catalogType={catalogType}
          editPath={basePath}
          label={label}
        />
      </div>
    </div>
  );
}
