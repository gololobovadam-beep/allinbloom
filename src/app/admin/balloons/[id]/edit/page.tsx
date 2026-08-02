import AdminCatalogProductEditorPage from "@/components/admin-catalog-product-editor-page";

export default async function EditBalloonPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AdminCatalogProductEditorPage catalogType="BALOONS" label="balloon" basePath="/admin/balloons" id={id} />;
}
