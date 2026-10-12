import { ChatMessage } from '@/app/geechat/geechat-types.ts'

export const EXAMPLE_MESSAGES: ChatMessage[] = [
  {
    type: 'message',
    room_id: 'room1',
    sender_id: 'user1',
    content: [
      { type: 'text', text: 'Hey, can you check the weather in New York and grab an image of it?' },
    ],
  },
  {
    type: 'message',
    room_id: 'room1',
    sender_id: 'assistant1',
    content: [
      { type: 'text', text: 'Sure! Let me check the weather for you first.' },
      {
        type: 'tool_call',
        name: 'get_weather',
        arguments: { location: 'New York', units: 'fahrenheit' },
        call_id: 'call1',
      },
    ],
  },
  {
    type: 'message',
    room_id: 'room1',
    sender_id: 'user',
    content: [
      {
        type: 'tool_call',
        name: 'get_weather',
        arguments: { location: 'New York', units: 'fahrenheit' },
        call_id: 'call1',
      },
      {
        type: 'tool_call_result',
        name: 'get_weather',
        arguments: { location: 'New York', units: 'fahrenheit' },
        call_id: 'call1',
        result: { temperature: 75, condition: 'Sunny', humidity: 42, wind_speed: 12 },
      },
    ],
  },
  {
    type: 'message',
    room_id: 'room1',
    sender_id: 'assistant1',
    content: [
      { type: 'text', text: 'Got it! The weather in New York is currently 75°F and sunny with 42% humidity.' },
      {
        type: 'tool_call',
        name: 'get_weather_image',
        arguments: { location: 'New York', style: 'realistic' },
        call_id: 'call2',
      },
    ],
  },
  {
    type: 'message',
    room_id: 'room1',
    sender_id: 'user1',
    content: [
      {
        type: 'tool_call_result',
        name: 'get_weather_image',
        arguments: { location: 'New York' },
        call_id: 'call2',
        error: 'Rate limit exceeded. Try again in 30s.',
      },
      { type: 'text', text: 'That\'s too bad about the image. Can you show me a random picture of new york?' },
    ],
  },
  {
    type: 'message',
    room_id: 'room1',
    sender_id: 'assistant1',
    content: [
      { type: 'text', text: 'Here\'s a picture of New York City for you!' },
      {
        type: 'image',
        url: 'https://images.unsplash.com/photo-1549924231-f129b911e442?w=400&q=60',
        alt: 'New York City skyline',
      },
    ],
  },
  {
    type: 'message',
    room_id: 'room1',
    sender_id: 'user1',
    content: [
      { type: 'text', text: 'Nice. Can you give me the geo coordinates of New York?' },
    ],
  },
  {
    type: 'message',
    room_id: 'room1',
    sender_id: 'assistant1',
    content: [
      { type: 'tool_call', name: 'get_geo_coordinates', arguments: { location: 'New York' }, call_id: 'call3' },
    ],
  },
  {
    type: 'message',
    room_id: 'room1',
    sender_id: 'assistant1',
    content: [
      {
        type: 'tool_call_result',
        name: 'get_geo_coordinates',
        arguments: { location: 'New York' },
        call_id: 'call3',
        result: { latitude: 40.7128, longitude: -74.0060 },
      },
      {
        type: 'text',
        text: 'The geo coordinates of New York City are approximately 40.7128° N latitude and 74.0060° W longitude.',
      },
    ],
  },
]