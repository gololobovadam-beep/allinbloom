import AdminCatalogManagementPage from "@/components/admin-catalog-management-page";

export default function AdminGiftsPage() {
  return (
    <AdminCatalogManagementPage
      catalogType="GIFTS"
      title="Manage Gift Box"
      label="Gift Box"
      basePath="/admin/gifts"
    />
  );
}
