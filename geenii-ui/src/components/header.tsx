import { PropsWithChildren } from "react";

const Header = ({children, title, subtitle, as, className}: PropsWithChildren<{title?: string, subtitle?: string, as?: any, className?: string}>) => {

  const ALLOWED_HEADERS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'];
  const DEFAULT_HEADER = 'h1';

  if (as && !ALLOWED_HEADERS.includes(as)) {
    console.warn(`Invalid header element "${as}". Falling back to "h2". Allowed values are: ${ALLOWED_HEADERS.join(', ')}`);
    as = DEFAULT_HEADER;
  }
  as = as || DEFAULT_HEADER;
  const HeaderElement = as || DEFAULT_HEADER;

  return (
        <div className={`mb-2 flex flex-column flex-wrap items-center justify-between space-y-2 gap-x-4`}>
            <div>
                <HeaderElement className={`text-2xl font-bold tracking-tight`}>{title}</HeaderElement>
                <p className='text-muted-foreground'>
                    {subtitle}
                </p>
            </div>
            {children}
        </div>
    );
};

export default Header;
