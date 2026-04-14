import asyncio
import asyncpg
import ssl

async def main():
    ssl_context = ssl.create_default_context(cafile='./global-bundle.pem')
    ssl_context.check_hostname = False
    
    conn = await asyncpg.connect('postgresql://postgres:Surplexcity@smartlms.cz4sm2yc07u6.ap-south-2.rds.amazonaws.com:5432/smartlms', ssl=ssl_context)
    res = await conn.fetch('SELECT status, course_id, student_id FROM enrollments LIMIT 10')
    print('Enrollments:')
    for row in res:
        print(row)
        
    res2 = await conn.fetch('SELECT count(*) FROM engagement_logs')
    print(f'Total engagement logs: {res2[0][0]}')
    
    await conn.close()

asyncio.run(main())
