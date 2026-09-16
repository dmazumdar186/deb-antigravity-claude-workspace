import { getBusiness } from '@/lib/business';
import Header from '@/components/Header';
import Hero from '@/components/Hero';
import TrustBar from '@/components/TrustBar';
import ServicesGrid from '@/components/ServicesGrid';
import BookingWidget from '@/components/BookingWidget';
import AboutLocation from '@/components/AboutLocation';
import Footer from '@/components/Footer';
import StickyMobileBar from '@/components/StickyMobileBar';

export default function Home() {
  // getBusiness() validates against business.schema.json and runs the
  // forbidden-term content linter — both throw and fail the build loudly.
  const business = getBusiness();

  return (
    <>
      <Header business={business} />
      <main>
        <Hero business={business} />
        <TrustBar business={business} />
        <ServicesGrid business={business} />
        <BookingWidget business={business} />
        <AboutLocation business={business} />
      </main>
      <Footer business={business} />
      <StickyMobileBar business={business} />
    </>
  );
}
