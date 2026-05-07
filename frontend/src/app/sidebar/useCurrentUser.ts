"use client";

import { useEffect, useState } from "react";

export interface CurrentUser {
  username: string;
  full_name: string;
  department: string;
  is_admin?: boolean;
}

function readCurrentUser() {
  const stored = localStorage.getItem("user");
  if (!stored) return null;
  try {
    return JSON.parse(stored) as CurrentUser;
  } catch {
    return null;
  }
}

export function useCurrentUser() {
  const [user, setUser] = useState<CurrentUser | null>(null);

  useEffect(() => {
    function syncUser() {
      setUser(readCurrentUser());
    }

    syncUser();
    window.addEventListener("user-updated", syncUser as EventListener);
    window.addEventListener("storage", syncUser);
    return () => {
      window.removeEventListener("user-updated", syncUser as EventListener);
      window.removeEventListener("storage", syncUser);
    };
  }, []);

  return user;
}
