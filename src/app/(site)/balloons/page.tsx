import type { Metadata } from "next";
import CatalogListing from "@/components/catalog-listing";

export const metadata: Metadata = {
  title: "Balloons | All in Bloom Floral Studio",
  description: "Explore balloons for birthdays, celebrations, and memorable moments.",
  alternates: { canonical: "/balloons" },
};

export default function BalloonsPage() {
  return (
    <CatalogListing
      catalogType="BALOONS"
      eyebrow="Balloons"
      title="Balloons for every celebration"
      description="Choose from our curated balloon designs for bright birthdays, thoughtful surprises, and every kind of special occasion."
      productLabel="balloons"
      emptyMessage="Our balloon collection is being refreshed. Please check back soon."
    />
  );
}
