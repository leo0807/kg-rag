import { redirect } from "next/navigation";

export default function GraphBuilderRedirectPage() {
  redirect("/cypher?tab=builder");
}
