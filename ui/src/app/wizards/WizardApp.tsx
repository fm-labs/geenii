import HSplitLayout from "../../ui/HSplitLayout.tsx";
import VSplitLayout from "../../ui/VSplitLayout.tsx";
import CompletionChatPage from "@/app/chat/completion-chat-page.tsx";
import TypewriterText from "../../ui/TypewriterText.tsx";

interface WizardAppProps {
    heading?: string;
}

const WizardApp = (props: WizardAppProps) => {
    //const [state, setState] = React.useState<WizardAppProps>({});
    const heading = props.heading || 'HelloScreen again';

    return (
        <div className={'Wizard-Container'}>
            <HSplitLayout
                left={
                    <div className={'Wizard-Chat p-5'}>
                        <h1 className={'text-center text-4xl mt-2 mb-5'}>{heading}</h1>

                        <div className={'text-center'}>
                            <TypewriterText text={'Hi, I\'m your personal assistant ! Ask me anything!'} className={'text-center mb-5'} />
                        </div>
                        <CompletionChatPage />
                    </div>
                }
                right={<>
                    <VSplitLayout
                        top={<div className={'WizardBox-Right-Top'}>
                            <h2>Step 1: Configuration</h2>
                            <CompletionChatPage />
                        </div>}
                        bottom={<div className={'WizardBox-Right-Bottom'}>
                            <h2>Step 2: Configuration</h2>
                            <CompletionChatPage />
                        </div>}
                        topClassName={'wizzard-top'}
                        bottomClassName={'wizzard-bottom'}
                    />
                </>}
                leftClassName={'wizzard-left'}
                rightClassName={'wizzard-right'}
                className={'wizzard-layout'}
            />
        </div>
    );
};

export default WizardApp;
