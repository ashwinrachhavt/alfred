import { NextResponse } from 'next/server';

export async function POST(req: Request) {
    try {
        const { messages, temperature = 0.7 } = await req.json();

        const apiKey = process.env.OPENAI_API_KEY;
        if (!apiKey) {
            return NextResponse.json({ error: 'Missing OPENAI_API_KEY' }, { status: 500 });
        }

        const response = await fetch('https://api.openai.com/v1/chat/completions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${apiKey}`,
            },
            body: JSON.stringify({
                model: 'gpt-4o',
                messages,
                temperature,
            }),
        });

        if (!response.ok) {
            const error = await response.json();
            return NextResponse.json({ error: error.error?.message || 'OpenAI API error' }, { status: response.status });
        }

        const data = await response.json();
        return NextResponse.json(data);
    } catch (error) {
        console.error('AI Request failed:', error);
        return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
    }
}
