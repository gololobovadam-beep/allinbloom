import type { Metadata } from "next";
import CatalogListing from "@/components/catalog-listing";

export const metadata: Metadata = {
  title: "Gift Box | All in Bloom Floral Studio",
  description: "Discover thoughtful gift boxes curated by All in Bloom Floral Studio.",
  alternates: { canonical: "/gifts" },
};

export default function GiftsPage() {
  return (
    <CatalogListing
      catalogType="GIFTS"
      eyebrow="Gift Box"
      title="Thoughtful gift boxes, beautifully chosen"
      description="A collection of elegant gifts for meaningful moments, ready to add to your order."
      cardVariant="gift"
      productLabel="gift boxes"
      emptyMessage="Our Gift Box collection is being curated. Please check back soon."
    />
  );
}
