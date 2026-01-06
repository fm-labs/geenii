const VSplitLayout = ({
                                 top,
                                 bottom,
                                 topHeight = 50, // Default to 50% height for the top section
                                 topClassName = '',
                                 bottomClassName = '',
                                 className = ''
                             }) => {

    const topStyle = { height: `${topHeight}%` };
    const bottomStyle = { height: `${100 - topHeight}%` };

    return (
        <div className={`flex flex-col h-screen w-full overflow-hidden ${className}`}>
            <div className={`flex-1 overflow-y-auto ${topClassName}`} style={topStyle}>
                {top}
            </div>
            <div className={`flex-1 overflow-y-auto ${bottomClassName}`} style={bottomStyle}>
                {bottom}
            </div>
        </div>
    );
};

export default VSplitLayout;
