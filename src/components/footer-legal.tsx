"use client";

import { useState } from "react";
import Modal from "@/components/modal";

type LegalSectionProps = {
  title: string;
  children: React.ReactNode;
};

function LegalSection({ title, children }: LegalSectionProps) {
  return (
    <section className="space-y-2 text-sm leading-6 text-stone-700">
      <h3 className="text-base text-stone-900">{title}</h3>
      {children}
    </section>
  );
}

export default function FooterLegal() {
  const [activeNotice, setActiveNotice] = useState<"privacy" | "processing" | null>(
    null
  );

  return (
    <>
      <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-[10px] uppercase tracking-[0.16em] text-stone-500 sm:text-xs sm:tracking-[0.22em]">
        <button
          type="button"
          onClick={() => setActiveNotice("privacy")}
          className="transition hover:text-stone-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-500 focus-visible:ring-offset-2"
        >
          Privacy Policy
        </button>
        <span aria-hidden="true" className="text-stone-300">
          /
        </span>
        <button
          type="button"
          onClick={() => setActiveNotice("processing")}
          className="transition hover:text-stone-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-stone-500 focus-visible:ring-offset-2"
        >
          Personal Data Notice
        </button>
      </div>

      <Modal
        open={activeNotice === "privacy"}
        onClose={() => setActiveNotice(null)}
        title="Privacy Policy"
        description="Effective date: August 2, 2026"
        panelClassName="legal-notice-modal max-w-3xl"
      >
        <div className="space-y-5">
          <LegalSection title="Our commitment">
            <p>
              All in Bloom Floral Studio (also called All in Bloom, we, us, or our)
              respects your privacy. This Privacy Policy explains how we collect, use,
              disclose, retain, and protect personal information when you visit our
              website, create an account, contact us, place an order, submit a review,
              or otherwise interact with us in the United States.
            </p>
          </LegalSection>

          <LegalSection title="Information we collect">
            <p>Depending on how you use our services, we may collect:</p>
            <ul className="list-disc space-y-1 pl-5 marker:text-stone-400">
              <li>
                contact and account details, such as your name, email address, phone
                number, and account profile information;
              </li>
              <li>
                order and delivery details, such as the recipient&apos;s information,
                delivery address, selected items, delivery preferences, messages, and
                purchase history;
              </li>
              <li>
                payment-related information supplied through our payment providers,
                such as payment status and transaction identifiers. Card and wallet
                credentials are processed by the payment provider, not stored by us;
              </li>
              <li>
                communications, reviews, photographs, and other content you choose to
                send to us; and
              </li>
              <li>
                limited technical information generated when you use the site, such as
                IP address, browser and device information, log data, and essential
                cookie data.
              </li>
            </ul>
          </LegalSection>

          <LegalSection title="How we use information">
            <p>We use personal information to:</p>
            <ul className="list-disc space-y-1 pl-5 marker:text-stone-400">
              <li>provide, process, deliver, and support orders and reservations;</li>
              <li>create and secure accounts, authenticate users, and prevent fraud;</li>
              <li>respond to requests, messages, reviews, and customer-service needs;</li>
              <li>maintain, troubleshoot, and improve our website and services;</li>
              <li>comply with legal, accounting, tax, and recordkeeping obligations; and</li>
              <li>protect the rights, safety, and property of All in Bloom and others.</li>
            </ul>
          </LegalSection>

          <LegalSection title="Cookies and third-party services">
            <p>
              We use essential cookies and similar technologies needed for sign-in,
              security, and site operation. Payment processors, mapping, authentication,
              chat, email, image-hosting, and social-media services that you elect to
              use may process information under their own privacy policies. Please
              review those providers&apos; notices before using their services.
            </p>
          </LegalSection>

          <LegalSection title="How we disclose information">
            <p>
              We disclose information only as needed to operate our business: to service
              providers that process payments, host the site, send email, provide
              delivery or customer-support tools, store images, or help secure our
              services; when required by law or a valid legal request; and in connection
              with a business transfer. We do not sell personal information for money or
              knowingly share it for cross-context behavioral advertising.
            </p>
          </LegalSection>

          <LegalSection title="Retention and security">
            <p>
              We retain information for as long as reasonably necessary for the purposes
              described here, including order fulfillment, customer support, legal and
              tax obligations, dispute resolution, and fraud prevention. We use
              reasonable administrative, technical, and organizational safeguards, but
              no method of internet transmission or storage is completely secure.
            </p>
          </LegalSection>

          <LegalSection title="Your privacy choices and U.S. state rights">
            <p>
              You may ask us to access, correct, delete, or provide a copy of certain
              personal information, subject to applicable law and our need to verify
              your request. Residents of states with comprehensive privacy laws,
              including California, may have additional rights to know, delete, correct,
              obtain a portable copy of data, opt out of certain processing, and appeal a
              decision about a privacy request. California residents may make a request
              under the California Consumer Privacy Act, as amended by the CPRA. We will
              not discriminate against you for exercising applicable privacy rights.
            </p>
            <p>
              To submit a request or appeal, email allinbloom.us@gmail.com with the
              subject line “Privacy Request.” We may ask for information needed to verify
              your identity and authority before acting on a request. Authorized agents
              may submit requests where state law permits.
            </p>
          </LegalSection>

          <LegalSection title="Children and updates">
            <p>
              Our services are not directed to children under 13, and we do not knowingly
              collect personal information from them. We may update this policy from time
              to time. The effective date above identifies the latest version.
            </p>
          </LegalSection>

          <LegalSection title="Contact us">
            <p>
              Questions about this policy can be sent to All in Bloom Floral Studio at
              allinbloom.us@gmail.com.
            </p>
          </LegalSection>
        </div>
      </Modal>

      <Modal
        open={activeNotice === "processing"}
        onClose={() => setActiveNotice(null)}
        title="Personal Data Processing Notice"
        description="Effective date: August 2, 2026"
        panelClassName="legal-notice-modal max-w-3xl"
      >
        <div className="space-y-5">
          <LegalSection title="Who is responsible for your data">
            <p>
              All in Bloom Floral Studio is responsible for the personal data described
              in this notice. For questions or requests, contact
              allinbloom.us@gmail.com.
            </p>
          </LegalSection>

          <LegalSection title="What data we process and why">
            <p>
              We process identity and contact details, account credentials, order and
              delivery details, communications, review content, and limited technical
              data. We use this data to administer accounts; quote, accept, and fulfill
              orders; arrange delivery; process payments through our payment providers;
              communicate with you; protect against fraud and misuse; and meet legal,
              financial, and operational obligations.
            </p>
          </LegalSection>

          <LegalSection title="When processing is permitted">
            <p>
              We process data when it is needed to provide a requested product or
              service, at your direction, to comply with law, to protect against fraud or
              security incidents, or for legitimate business operations consistent with
              applicable law. When consent is required, we will request it and you may
              withdraw it for future processing.
            </p>
          </LegalSection>

          <LegalSection title="Recipients and service providers">
            <p>
              Access is limited to personnel and providers who need the information to do
              their work for us. These may include payment processors, hosting and
              security providers, email and customer-support tools, image-storage
              providers, delivery partners, and professional advisers. Providers are
              permitted to process information only as necessary to provide their
              services, subject to their applicable agreements and privacy notices.
            </p>
          </LegalSection>

          <LegalSection title="Payment data">
            <p>
              Payments are handled through third-party payment providers. We do not store
              full payment-card numbers or security codes on our systems. We may receive
              limited payment confirmation, transaction, and anti-fraud information needed
              to complete, reconcile, and support your order.
            </p>
          </LegalSection>

          <LegalSection title="Retention, location, and protection">
            <p>
              We retain data only for the period reasonably necessary for the purposes
              above, including customer support, accounting, tax, fraud prevention, and
              legal requirements. Our service providers may process data in the United
              States or other jurisdictions where they operate. We apply reasonable
              safeguards appropriate to the nature of the information, while recognizing
              that no system can guarantee absolute security.
            </p>
          </LegalSection>

          <LegalSection title="Your requests">
            <p>
              Subject to applicable law, you may request access to, correction of,
              deletion of, or a copy of your personal data, and may ask questions about
              our processing. Email allinbloom.us@gmail.com with the subject line
              “Personal Data Request.” We will verify the request before responding and
              may retain limited information where law permits or requires it.
            </p>
          </LegalSection>

          <LegalSection title="Changes to this notice">
            <p>
              We may revise this notice as our services or legal obligations change. The
              effective date above indicates when this version took effect.
            </p>
          </LegalSection>
        </div>
      </Modal>
    </>
  );
}
