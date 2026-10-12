
type AgentType = {
  id: string;
  name: string;
  description: string;
  model: string;
  tools?: string[];
  skills?: string[];
  imageUrl?: string;
}