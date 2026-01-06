 import {DetailedHTMLProps, PropsWithChildren} from 'react';

export const Container = ({children, ...props}: PropsWithChildren & DetailedHTMLProps<any, HTMLDivElement>) => {
    return (
        <div {...props}>
            {children}
        </div>
    );
};

export default Container;
