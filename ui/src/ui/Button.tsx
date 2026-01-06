import {DetailedHTMLProps, PropsWithChildren} from 'react';

export const Button = ({children, ...props}: PropsWithChildren & DetailedHTMLProps<any, HTMLButtonElement>) => {
    return (
        <button className="px-4 py-2 bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors" {...props}>
            {children}
        </button>
    );
};

export default Button;
