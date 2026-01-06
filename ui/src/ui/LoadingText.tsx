
interface LoadingTextProps {
    text?: string;
    show?: boolean;
}

const LoadingText = (props) => {
    const { text = "Loading...", show = true } = props as LoadingTextProps;

    if (!show) {
        return null;
    }

    return (
        <span>
            {text}
        </span>
    );
};

export default LoadingText;
