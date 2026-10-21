import {test,expect} from '@playwright/test';

test('login, admin users, editable inventory and sign out',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');
 await expect(page.getByRole('heading',{name:'Sign in to your journey.'})).toBeVisible();
 await page.screenshot({path:'../../artifacts/login-desktop.png',fullPage:true});
 await page.getByLabel('Email address').fill('admin@routerescue.local');
 await page.getByLabel('Password',{exact:true}).fill('wrong-password');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('incorrect');
 await page.getByLabel('Password',{exact:true}).fill('Admin@12345');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('heading',{name:'A clearer view of every journey.'})).toBeVisible();
 await page.screenshot({path:'../../artifacts/admin-desktop.png',fullPage:true});
 await page.getByRole('button',{name:'Users',exact:true}).click();
 await expect(page.locator('tbody tr')).toHaveCount(5);
 await expect(page.getByText('aarav@routerescue.local',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Trips & inventory',exact:true}).click();
 await page.getByRole('button').filter({hasText:"Aarav's Bengaluru getaway"}).click();
 await expect(page.getByRole('heading',{name:'Searchable inventory'})).toBeVisible();
 const offer=page.locator('.inventory-editor').first();
 await offer.getByLabel('Total per traveller (₹)').fill('3300');
 await offer.getByRole('button',{name:'Save offer'}).click();
 await expect(offer.getByText('Offer A · version 2')).toBeVisible();
 await page.getByRole('button',{name:'Connections',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Agent connections'})).toBeVisible();
 await page.getByRole('button',{name:'Sign out',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Sign in to your journey.'})).toBeVisible();
 expect(errors).toEqual([]);
});

test('mobile login and separate seeded traveller trips',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/');
 await page.screenshot({path:'../../artifacts/login-mobile.png',fullPage:true});
 await page.getByLabel('Email address').fill('meera@routerescue.local');
 await page.getByLabel('Password',{exact:true}).fill('Meera@12345');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Let’s keep your trip on track.'})).toBeVisible();
 await expect(page.getByRole('combobox',{name:'Select trip'})).toBeVisible();
 await expect(page.getByRole('combobox',{name:'Select trip'}).locator('option')).toHaveCount(2);
 const result=await page.request.get('/api/trips');
 const trips=await result.json();
 expect(trips).toHaveLength(2);
 expect(trips.every((trip:{title:string})=>trip.title.startsWith("Meera's"))).toBe(true);
 expect((await page.request.get('/api/admin/overview')).status()).toBe(403);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
});
