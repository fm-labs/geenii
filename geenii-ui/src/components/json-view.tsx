import React from 'react'
import ReactJson, { ReactJsonViewProps } from '@microlink/react-json-view'
import { cn } from '@/lib/utils.ts'
import { Button } from './ui/button';
import { CheckIcon, CopyIcon } from 'lucide-react'

type JsonViewProps = ReactJsonViewProps & {
  src: any;
  collapsed?: boolean;
  className?: string;
}


const JsonView = ({src, collapsed, className, ...props}: JsonViewProps) => {

  const defaultClassName = "max-w-[500px]"
  const clsName = cn(defaultClassName, className)

  const [isCopied, setIsCopied] = React.useState(false);

  const copyToClipboard = (value: string) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(value).then(() => {
        console.log('Copied to clipboard:', value);
        setIsCopied(true);
      }).catch(err => {
        console.error('Failed to copy to clipboard:', err);
      });
    } else {
      console.warn('Clipboard API not supported');
    }
  }

  return (
    <div className={"rounded-md border bg-muted p-2 overflow-y-scroll mb-2 max-h-100 "}>
      <div className={"flex justify-start mb-2 text-sm text-muted-foreground gap-1"}>
        <div>
          <Button size={"sm"} variant={"secondary"} title={"Copy"}
                  onClick={() => copyToClipboard(JSON.stringify(src, null, 2))}>
            <CopyIcon className={"hover:bg-accent accent-green-700"} />
          </Button>
        </div>
        {isCopied && <div className={"py-2"}>Copied to clipboard</div>}
      </div>
      <pre className={clsName}>{JSON.stringify(src, null, 2)}</pre>
    </div>
  )
}

export default JsonView