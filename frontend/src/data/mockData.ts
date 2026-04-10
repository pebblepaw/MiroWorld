export type AgentSentiment = "positive" | "neutral" | "negative";

export interface Agent {
  id: string;
  name: string;
  age: number;
  gender: string;
  ethnicity: string;
  occupation: string;
  planningArea: string;
  incomeBracket: string;
  housingType?: string;
  sentiment: AgentSentiment;
  approvalScore: number;
}

export interface SimComment {
  id?: string;
  agentName: string;
  agentOccupation?: string;
  content: string;
  upvotes: number;
}

export interface SimPost {
  id: string;
  agentId: string;
  agentName: string;
  agentOccupation: string;
  agentArea: string;
  title: string;
  content: string;
  upvotes: number;
  downvotes: number;
  commentCount: number;
  round: number;
  timestamp: string;
  comments: SimComment[];
}

const FIRST_NAMES = [
  "Aisyah",
  "Ahmad",
  "Alex",
  "Amir",
  "Celine",
  "Daryl",
  "Farah",
  "Grace",
  "Hafiz",
  "Janet",
  "Jia",
  "Karthik",
  "Marcus",
  "Mei",
  "Nora",
  "Priya",
  "Raj",
  "Siti",
  "Tan",
  "Wei",
];

const LAST_NAMES = [
  "Abdullah",
  "Chen",
  "Ho",
  "Ibrahim",
  "Kumar",
  "Lee",
  "Lim",
  "Nair",
  "Ng",
  "Pillai",
  "Rahman",
  "Santos",
  "Tan",
  "Wong",
  "Yeo",
];

const OCCUPATIONS = [
  "Teacher",
  "Nurse",
  "Software Engineer",
  "Taxi Driver",
  "Retail Manager",
  "Civil Servant",
  "Delivery Rider",
  "Marketing Executive",
  "Accountant",
  "Hawker",
  "Property Agent",
  "Technician",
  "Healthcare Assistant",
  "Small Business Owner",
  "Student",
];

const PLANNING_AREAS = [
  "Woodlands",
  "Jurong West",
  "Punggol",
  "Sengkang",
  "Toa Payoh",
  "Queenstown",
  "Ang Mo Kio",
  "Yishun",
  "Tampines",
  "Bukit Batok",
  "Bedok",
  "Pasir Ris",
];

const INCOME_BRACKETS = [
  "Below $2,000",
  "$2,000-$4,000",
  "$4,000-$6,000",
  "$6,000-$8,000",
  "$8,000-$10,000",
  "Above $10,000",
];

const HOUSING_TYPES = [
  "2-Room",
  "3-Room",
  "4-Room",
  "5-Room",
  "Executive",
  "Condo",
];

const GENDERS = ["Male", "Female"];
const ETHNICITIES = ["Chinese", "Malay", "Indian", "Eurasian", "Filipino"];

const POSITIVE_RESPONSES = [
  "I support the direction, but implementation details still matter.",
  "The policy could work if the rollout remains transparent and practical.",
  "I see potential benefits here, especially with stronger safeguards.",
  "This looks promising if support reaches ordinary households early.",
];

const NEUTRAL_RESPONSES = [
  "I can see tradeoffs on both sides and need more concrete evidence.",
  "The overall direction is unclear until implementation details are published.",
  "I am waiting for clearer district-level impact data before deciding.",
  "Some parts make sense, but the fairness questions are still unresolved.",
];

const NEGATIVE_RESPONSES = [
  "This still feels like it shifts costs onto working households.",
  "I am not convinced the current proposal protects lower-income residents.",
  "The benefits sound abstract while the downsides feel immediate.",
  "Without stronger safeguards, this policy could deepen existing pressure points.",
];

export const agentResponses: Record<AgentSentiment, string[]> = {
  positive: POSITIVE_RESPONSES,
  neutral: NEUTRAL_RESPONSES,
  negative: NEGATIVE_RESPONSES,
};

function seededValue(seed: number): number {
  const normalized = Math.imul(seed ^ 0x45d9f3b, 0x45d9f3b);
  return (normalized >>> 0) / 0xffffffff;
}

function pick<T>(values: T[], seed: number): T {
  return values[Math.floor(seededValue(seed) * values.length) % values.length];
}

function sentimentForIndex(index: number): AgentSentiment {
  const roll = seededValue(index * 17 + 11);
  if (roll < 0.34) return "negative";
  if (roll < 0.68) return "neutral";
  return "positive";
}

function approvalScoreForSentiment(sentiment: AgentSentiment, index: number): number {
  const base = seededValue(index * 29 + 7);
  if (sentiment === "positive") {
    return 65 + Math.round(base * 27);
  }
  if (sentiment === "negative") {
    return 12 + Math.round(base * 27);
  }
  return 45 + Math.round(base * 18);
}

export function generateAgents(count: number): Agent[] {
  return Array.from({ length: Math.max(0, count) }, (_, index) => {
    const id = `demo-agent-${String(index + 1).padStart(3, "0")}`;
    const sentiment = sentimentForIndex(index);
    const firstName = pick(FIRST_NAMES, index * 3 + 1);
    const lastName = pick(LAST_NAMES, index * 5 + 2);
    const age = 18 + Math.floor(seededValue(index * 13 + 3) * 55);

    return {
      id,
      name: `${firstName} ${lastName}`,
      age,
      gender: pick(GENDERS, index * 7 + 4),
      ethnicity: pick(ETHNICITIES, index * 11 + 5),
      occupation: pick(OCCUPATIONS, index * 13 + 6),
      planningArea: pick(PLANNING_AREAS, index * 17 + 8),
      incomeBracket: pick(INCOME_BRACKETS, index * 19 + 9),
      housingType: pick(HOUSING_TYPES, index * 23 + 10),
      sentiment,
      approvalScore: approvalScoreForSentiment(sentiment, index),
    };
  });
}
