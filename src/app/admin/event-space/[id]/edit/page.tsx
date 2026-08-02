import AdminCatalogProductEditorPage from "@/components/admin-catalog-product-editor-page";

export default async function EditEventSpacePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <AdminCatalogProductEditorPage catalogType="EVENT_SPACE" label="event space" basePath="/admin/event-space" id={id} />;
}
