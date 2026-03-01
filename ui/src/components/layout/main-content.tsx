import { PropsWithChildren } from "react";

const MainContent = ({children}: PropsWithChildren<any>) => {
    return (
      <main className={"absolute top-16 left-0 w-full h-[calc(100vh-4rem)] overflow-hidden"}>
        <div className="content max-w-7xl mx-auto">
          <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6 px-4 flex-1 overflow-auto min-h-[90vh]">
              {children}
          </div>
        </div>
      </main>
    );
};

export default MainContent;
