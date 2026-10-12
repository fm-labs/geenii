import { Button } from '@/components/ui/button'
import { useNavigate } from '@/app-router.tsx'

export function UnauthorisedError() {
  const navigate = useNavigate()

  const currentPath = window.location.pathname;

  return (
    <div className='h-svh'>
      <div className='m-auto flex h-full w-full flex-col items-center justify-center gap-2'>
        <h1 className='text-[7rem] leading-tight font-bold'>401</h1>
        <span className='font-medium'>Unauthorized Access</span>
        <p className='text-muted-foreground text-center'>
          Please log in with the appropriate credentials <br /> to access this
          resource.
        </p>
        <div className='mt-6 flex gap-4'>
          <Button variant={'outline'} onClick={() => navigate('/')}>Back to Home</Button>
          <Button onClick={() => navigate(`/auth/login?redirect=${currentPath}`)}>Go to Login</Button>
        </div>
      </div>
    </div>
  )
}
