import React from "react";

interface QuickCompletionProps {
    defaultPrompt?: string;
    onSubmit: (prompt: string) => Promise<void>;
}

const QuickCompletion = (props: QuickCompletionProps) => {
    const [prompt, setPrompt] = React.useState(props.defaultPrompt);
    const [isSubmitting, setIsSubmitting] = React.useState(false);

    const handleSubmit = async () => {
        console.log("Submitting prompt:", prompt);
        if (props.onSubmit) {
            setIsSubmitting(true);
            await props
              .onSubmit(prompt)
              .finally(() => setIsSubmitting(false));
        }
    }

    return (
        <div>
            <div>
                <textarea
                    className="w-full h-32 p-2 border border-gray-300 rounded-md"
                    placeholder="Type your prompt here..."
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                ></textarea>

                <button
                    className="mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    onClick={handleSubmit}
                    disabled={isSubmitting || prompt?.trim().length === 0}
                >Submit
                </button>
            </div>
        </div>
    );
};

export default QuickCompletion;
