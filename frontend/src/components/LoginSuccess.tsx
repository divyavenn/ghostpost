import { useEffect } from 'react';

export function LoginSuccess() {
  useEffect(() => {
    // Extract username from URL params, store it, and redirect immediately
    const params = new URLSearchParams(window.location.search);
    const username = params.get('username');

    if (username) {
      localStorage.setItem('username', username);
    }

    // Redirect to home immediately
    window.location.href = '/';
  }, []);

  // Brief loading state while redirect happens
  return null;
}
