import {DetailedHTMLProps, PropsWithChildren} from 'react';

export const Badge = ({children, ...props}: PropsWithChildren & DetailedHTMLProps<any, HTMLDivElement>) => {
    return (
        <div {...props}>
            {children}
        </div>
    );
};

export default Badge;