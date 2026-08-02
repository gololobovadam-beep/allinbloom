import type { Metadata } from "next";
import CatalogListing from "@/components/catalog-listing";

export const metadata: Metadata = {
  title: "Gifts | All in Bloom Floral Studio",
  description: "Discover thoughtful gifts curated by All in Bloom Floral Studio.",
  alternates: { canonical: "/gifts" },
};

export default function GiftsPage() {
  return (
    <CatalogListing
      catalogType="GIFTS"
      eyebrow="Gifts"
      title="Thoughtful gifts, beautifully chosen"
      description="A collection of elegant gifts for meaningful moments, ready to add to your order."
      cardVariant="gift"
      productLabel="gifts"
      emptyMessage="Our gift collection is being curated. Please check back soon."
    />
  );
}
