export type PageGuide = {
  title: string;
  summary: string;
  features: string[];
  actions: string[];
  related: { label: string; href: string }[];
};

export type GuideEntry = {
  match: string | RegExp;
  key: string;
  guide: PageGuide;
};
