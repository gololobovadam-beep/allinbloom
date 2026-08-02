import {
  BOUQUET_TYPES,
  FLOWER_TYPES_WITH_MIXED,
} from "@/lib/constants";

export type FlowerType = (typeof FLOWER_TYPES_WITH_MIXED)[number];
export type BouquetType = (typeof BOUQUET_TYPES)[number];
export type CatalogType = "FLOWERS" | "BALOONS" | "GIFTS" | "EVENT_SPACE";
export type OrderStatus = "PENDING" | "PAID" | "FAILED" | "CANCELED";

export type CatalogCategory = {
  id: string;
  catalogType: CatalogType;
  slug: string;
  name: string;
  position: number;
  isActive: boolean;
};

export type EventTier = {
  id: string;
  priceCents: number;
  description: string;
};

export type Bouquet = {
  id: string;
  /**
   * Optional while older API payloads are still cached. The public catalog
   * treats an omitted value as FLOWERS for backwards compatibility.
   */
  catalogType?: CatalogType;
  categoryId?: string | null;
  category?: CatalogCategory | null;
  name: string;
  description: string;
  priceCents: number;
  currency: string;
  flowerType: FlowerType;
  style: string;
  bouquetType: BouquetType;
  colors: string;
  isMixed: boolean;
  isFeatured: boolean;
  isActive: boolean;
  isSoldOut: boolean;
  allowFlowerQuantity: boolean;
  defaultFlowerQuantity: number;
  discountPercent: number;
  discountNote: string | null;
  videoUrl?: string | null;
  /** Ordered gallery. Public galleries deliberately expose only its first six images. */
  galleryImages?: string[];
  tiers?: EventTier[];
  image: string;
  image2: string | null;
  image3: string | null;
  image4: string | null;
  image5: string | null;
  image6: string | null;
};

export type PromoSlide = {
  id: string;
  title: string;
  subtitle: string | null;
  image: string;
  link: string | null;
  isActive: boolean;
  position: number;
};

export type Review = {
  id: string;
  name: string;
  rating: number;
  text: string;
  image: string | null;
  createdAt: string;
};

export type AdminReview = Review & {
  email: string;
  isActive: boolean;
  isRead: boolean;
  updatedAt: string;
};

export type OrderItem = {
  id: string;
  orderId: string;
  bouquetId: string | null;
  name: string;
  priceCents: number;
  quantity: number;
  image: string;
  details: string | null;
};

export type Order = {
  id: string;
  email: string | null;
  phone: string | null;
  stripeSessionId: string | null;
  paypalOrderId: string | null;
  paypalCaptureId: string | null;
  totalCents: number;
  currency: string;
  status: OrderStatus;
  isRead: boolean;
  deliveryAddress: string | null;
  deliveryAddressLine1: string | null;
  deliveryAddressLine2: string | null;
  deliveryCity: string | null;
  deliveryState: string | null;
  deliveryPostalCode: string | null;
  deliveryCountry: string | null;
  deliveryFloor: string | null;
  deliveryDateTime: string | null;
  orderComment: string | null;
  deliveryMiles: string | null;
  deliveryFeeCents: number | null;
  firstOrderDiscountPercent: number | null;
  paymentFailureStage: string | null;
  paymentFailureCode: string | null;
  paymentFailureMessage: string | null;
  paymentFailureDetails: string | null;
  paymentFailedAt: string | null;
  createdAt: string;
  items: OrderItem[];
};

export type StoreSettings = {
  id: string;
  globalDiscountPercent: number;
  globalDiscountNote: string | null;
  categoryDiscountPercent: number;
  categoryDiscountNote: string | null;
  categoryFlowerType: string | null;
  categoryStyle: string | null;
  categoryMixed: string | null;
  categoryColor: string | null;
  categoryMinPriceCents: number | null;
  categoryMaxPriceCents: number | null;
  firstOrderDiscountPercent: number;
  firstOrderDiscountNote: string | null;
  homeHeroImage: string;
  homeGalleryImage1: string;
  homeGalleryImage2: string;
  homeGalleryImage3: string;
  homeGalleryImage4: string;
  homeGalleryImage5: string;
  homeGalleryImage6: string;
  /** Ordered gallery stored independently from the legacy six slots. */
  homeGalleryImages?: string[];
  catalogCategoryImageMono: string;
  catalogCategoryImageMixed: string;
  catalogCategoryImageSeason: string;
  catalogCategoryImageAll: string;
};

export type DiscountInfo = {
  percent: number;
  note: string;
  source: "bouquet" | "category" | "global";
};

export type BouquetPricing = {
  originalPriceCents: number;
  finalPriceCents: number;
  discount: DiscountInfo | null;
};

export type CatalogItem = {
  bouquet: Bouquet;
  pricing: BouquetPricing;
};

export type CatalogResponse = {
  items: CatalogItem[];
  nextCursor: string | null;
};

export type OrderStripeAddress = {
  line1: string | null;
  line2: string | null;
  city: string | null;
  state: string | null;
  postalCode: string | null;
  country: string | null;
};

export type OrderStripeShipping = {
  name: string | null;
  phone: string | null;
  address: OrderStripeAddress | null;
};

export type OrderStripeSession = {
  paymentStatus: string | null;
  status: string | null;
  created: number | null;
  expiresAt: number | null;
  paymentIntentId: string | null;
  paymentIntentStatus: string | null;
  lastPaymentErrorCode: string | null;
  lastPaymentErrorDeclineCode: string | null;
  lastPaymentErrorMessage: string | null;
  latestChargeId: string | null;
  latestChargeStatus: string | null;
  chargeFailureCode: string | null;
  chargeFailureMessage: string | null;
  chargeOutcomeType: string | null;
  chargeOutcomeReason: string | null;
  chargeOutcomeNetworkStatus: string | null;
  chargeOutcomeSellerMessage: string | null;
  cardBrand: string | null;
  cardFunding: string | null;
  cardCountry: string | null;
  cardCheckAddressPostalCode: string | null;
  cardCheckCvc: string | null;
  shipping: OrderStripeShipping | null;
  deliveryAddress: string | null;
  deliveryDateTime: string | null;
  deliveryMiles: string | null;
  deliveryFeeCents: number | null;
  firstOrderDiscountPercent: number | null;
};

export type PaymentEvent = {
  id: string;
  orderId: string;
  provider: string;
  source: string;
  event: string;
  message: string | null;
  stripeSessionId: string | null;
  stripeEventId: string | null;
  paymentIntentId: string | null;
  context: Record<string, unknown> | null;
  createdAt: string;
};
