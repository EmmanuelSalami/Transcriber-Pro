'use client';

import { usePathname } from 'next/navigation';
import { NavBar } from './NavBar';

export function ConditionalNavBar() {
  const pathname = usePathname();
  if (pathname?.startsWith('/auth')) {
    return null;
  }
  return <NavBar />;
}
