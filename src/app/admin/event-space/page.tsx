import AdminCatalogManagementPage from "@/components/admin-catalog-management-page";

export default function AdminEventSpacePage() {
  return (
    <AdminCatalogManagementPage
      catalogType="EVENT_SPACE"
      title="Manage event space"
      label="Event spaces"
      basePath="/admin/event-space"
    />
  );
}
