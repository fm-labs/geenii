import { PropsWithChildren } from "react";

const Header = ({children, title, subtitle}: PropsWithChildren<{title?: string, subtitle?: string}>) => {
    return (
        <div className='mb-2 flex flex-column flex-wrap items-center justify-between space-y-2 gap-x-4'>
            <div>
                <h2 className='text-2xl font-bold tracking-tight'>{title}</h2>
                <p className='text-muted-foreground'>
                    {subtitle}
                </p>
            </div>
            {children}
        </div>
    );
};

export default Header;
