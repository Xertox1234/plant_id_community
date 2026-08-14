import type { ReactNode } from 'react';

interface RailModuleProps {
  icon: ReactNode;
  title: string;
  children: ReactNode;
}

export default function RailModule({ icon, title, children }: RailModuleProps) {
  return (
    <section className="flex flex-col gap-3.5">
      <h4 className="flex items-center gap-2 text-[13px] font-semibold [&>svg]:h-[15px] [&>svg]:w-[15px] [&>svg]:text-secondary">
        {icon}
        {title}
      </h4>
      {children}
    </section>
  );
}
