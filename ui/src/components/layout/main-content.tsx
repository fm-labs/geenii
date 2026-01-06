import { PropsWithChildren } from "react";

const MainContent = ({children}: PropsWithChildren<any>) => {
    return (
        <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 flex-1 overflow-auto min-h-[90vh]">
            {children}
        </div>
    );
};

export default MainContent;
