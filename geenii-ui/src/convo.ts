import { ChatMessage } from '@/app/chat/components/chat.types.ts'

export const convo: ChatMessage[] = [
  {
    role: 'user',
    content: [{ type: 'text', text: 'Hello, how are you?' }],
  },
  {
    role: 'assistant',
    content: [{ type: 'text', text: 'I am fine, thank you! How can I assist you today?' }],
  },
  {
    role: 'user',
    content: [{ type: 'text', text: 'Can you show me a code snippet?' }],
  },
  {
    role: 'assistant',
    content: [
      { type: 'text', text: 'Sure! Here is a simple JavaScript function:' },
      { type: 'code', text: 'function greet(name) {\n  return `Hello, ${name}!`;\n}' },
    ],
  },
  {
    role: 'user',
    content: [{ type: 'text', text: 'Can you show get the current weather for me? (use a tool function)' }],
  },
  {
    role: 'assistant',
    content: [
      { type: 'text', text: 'Sure! Let me fetch the current weather for you.' },
      { type: 'function', function: { name: 'get_current_weather', args: { location: 'San Francisco, CA' } } },
      {
        type: 'approval',
        id: 'approval-1',
        data: { scope: 'REQUEST' },
        text: 'The assistant is requesting to call the function "get_current_weather" with the argument location: "San Francisco, CA". Do you approve?',
      },
    ],
  },
  // user sends another message with approving the function call
  {
    role: 'user',
    content: [
      { type: 'approval', data: { scope: 'RESPONSE', requestId: 'approval-1' }, text: 'APPROVE' },
      //{ type: 'function_permission', function: { name: 'get_current_weather', args: { location: 'San Francisco, CA' } }, content: "ALLOW_ONCE" },
      //{ type: 'function', function: { name: 'get_current_weather', args: { location: 'San Francisco, CA' } } }
    ],
  },
  {
    role: 'assistant',
    content: [
      { type: 'text', text: 'Here is the current weather for San Francisco, CA:' },
      {
        type: 'function',
        function: { name: 'get_current_weather', args: { location: 'San Francisco, CA' } },
        data: { 'temperature': '68°F' },
      },
      { type: 'text', text: 'It is currently 68°F with clear skies.' },
      { type: 'text', text: 'No need for a rain coat ;)' },
    ],
  },
  // now user wants to see an image
  {
    role: 'user',
    content: [{ type: 'text', text: 'Can you show me an image of a cute puppy?' }],
  },
  {
    role: 'assistant',
    content: [
      { type: 'text', text: 'Sure! Here is an image of a cute puppy:' },
      { type: 'image', data: { url: 'https://placedog.net/500' } },
      { type: 'text', text: 'Or maybe you like this one that I rendered for you' },
      { type: 'image', data: { base64: '' } },
    ],
  },
]