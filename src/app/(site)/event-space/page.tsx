import type { Metadata } from "next";
import CatalogListing from "@/components/catalog-listing";

export const metadata: Metadata = {
  title: "Event Space | All in Bloom Floral Studio",
  description: "Explore All in Bloom event-space options and booking tiers.",
  alternates: { canonical: "/event-space" },
};

export default function EventSpacePage() {
  return (
    <CatalogListing
      catalogType="EVENT_SPACE"
      eyebrow="Event space"
      title="Make the moment yours"
      description="Explore our event-space options, discover the right tier for your celebration, and book directly with our studio."
      cardVariant="event"
      productLabel="event spaces"
      emptyMessage="Event-space options are coming soon. Please contact our studio for availability."
      includeFirstOrderDiscount={false}
    />
  );
}
