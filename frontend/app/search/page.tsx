import { Suspense } from "react";
import { SearchPageClient } from "./search-page-client";

export default function SearchPage() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-500">加载中</p>}>
      <SearchPageClient />
    </Suspense>
  );
}
