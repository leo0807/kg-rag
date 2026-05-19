import { redirect } from "next/navigation";

export default function AdminCypherRedirectPage() {
  redirect("/cypher?tab=admin");
}
