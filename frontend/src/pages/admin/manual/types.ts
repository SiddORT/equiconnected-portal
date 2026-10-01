export interface ManualTopic {
  id: string;
  title: string;
  purpose: string;
  where: string;
  who: string;
  prerequisites: string[];
  steps: string[];
  result: string;
  restrictions: string[];
  images?: { src: string; alt: string; caption: string }[];
}

export interface ManualSection {
  title: string;
  topics: ManualTopic[];
}