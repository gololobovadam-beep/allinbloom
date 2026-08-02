import AdminCatalogManagementPage from "@/components/admin-catalog-management-page";

export default function AdminBalloonsPage() {
  return (
    <AdminCatalogManagementPage
      catalogType="BALOONS"
      title="Manage balloons"
      label="Balloons"
      basePath="/admin/balloons"
    />
  );
}
