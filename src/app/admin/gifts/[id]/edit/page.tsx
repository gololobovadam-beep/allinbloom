import AdminCatalogProductEditorPage from "@/components/admin-catalog-product-editor-page";

export default async function EditGiftPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AdminCatalogProductEditorPage catalogType="GIFTS" label="gift" basePath="/admin/gifts" id={id} />;
}
