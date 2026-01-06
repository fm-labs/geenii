const HSplitLayout = ({
                          left,
                          right,
                          leftWidth = 50,
                          leftClassName = "",
                          rightClassName = "",
                          className = "",
                      }) => {

    const leftStyle = { width: `${leftWidth}%` };
    const rightStyle = { width: `${100 - leftWidth}%` };

    return (
        <div className={`flex h-screen w-full overflow-hidden ${className}`}>
            <div style={leftStyle}
                 className={`flex-1 overflow-y-auto border-r border-r-gray-200 ${leftClassName}`}>
                {left}
            </div>
            <div style={rightStyle}
                 className={`flex-1 overflow-y-auto ${rightClassName}`}>
                {right}
            </div>
        </div>
    );
};

export default HSplitLayout;
