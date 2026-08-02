import AdminCatalogManagementPage from "@/components/admin-catalog-management-page";

export default function AdminGiftsPage() {
  return (
    <AdminCatalogManagementPage
      catalogType="GIFTS"
      title="Manage gifts"
      label="Gifts"
      basePath="/admin/gifts"
    />
  );
}
